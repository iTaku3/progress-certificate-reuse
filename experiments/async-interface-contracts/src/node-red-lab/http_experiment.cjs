'use strict';
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto');
const helper=require('node-red-node-test-helper');
const httpFile=require.resolve('@node-red/nodes/core/network/21-httprequest.js');
const httpNode=require(httpFile);
const root=path.resolve(__dirname,'../..');
const args=process.argv.slice(2);const oi=args.indexOf('--output');
const out=oi<0?path.join(root,'outputs/http'):path.resolve(args[oi+1]);
const deadline=Date.parse('2026-09-08T11:00:00+09:00');
function check(){if(args.includes('--enforce-deadline')&&Date.now()>=deadline)throw Error('Research deadline reached');}
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const save=(n,x)=>fs.writeFileSync(path.join(out,n),JSON.stringify(x,null,2)+'\n');
function inputs(){
 const graphs=[{name:'clique2',n:2,edges:[[0,1]]},{name:'path3',n:3,edges:[[0,1],[1,2]]},{name:'empty3',n:3,edges:[]},{name:'cycle4',n:4,edges:[[0,1],[1,2],[2,3],[0,3]]}];
 const result=[];
 for(const graph of graphs)for(const mode of ['end_200','accept_202','client_timeout'])for(let seed=0;seed<3;seed++){
  result.push({id:`${graph.name}_${mode}_${seed}`,graph,mode,seed,requestTimeout:mode==='client_timeout'?65+seed*10:2000,
   jobs:Array.from({length:graph.n},(_,id)=>({id,startDelay:5+(id+seed)%3,duration:180+seed*25+id*20})),pollMs:30});
 }
 return result;
}
async function run(input,policy){
 const trace=[],active=new Set(),held=new Set(),waiting=[...input.jobs],dispatched=new Set(),terminals=new Set(),ended=new Set(),serverJobs=new Map(),timers=new Set(),pollers=new Map();
 let gate,violation=false,maxActive=0,settled=false,resolveCase,rejectCase;
 const start=process.hrtime.bigint();const record=(event,id,extra={})=>trace.push({index:trace.length,event,id,elapsedMs:Number(process.hrtime.bigint()-start)/1e6,...extra});
 const done=new Promise((resolve,reject)=>{resolveCase=resolve;rejectCase=reject;});
 const later=(fn,ms)=>{const t=setTimeout(()=>{timers.delete(t);try{fn();}catch(e){rejectCase(e);}},ms);timers.add(t);return t;};
 const conflict=(a,b)=>input.graph.edges.some(([x,y])=>(a===x&&b===y)||(a===y&&b===x));
 function settle(status){if(!settled){settled=true;resolveCase(status);}}
 function inspect(){
  if(waiting.length===0&&ended.size===input.graph.n&&terminals.size===input.graph.n&&(policy!=='confirm_status'||held.size===0))settle('complete');
  if(policy==='release_on_2xx'&&waiting.length>0&&dispatched.size>0&&ended.size===dispatched.size&&terminals.size===dispatched.size)settle('stalled');
 }
 const server=http.createServer((req,res)=>{
  const u=new URL(req.url,'http://127.0.0.1');
  if(req.method==='POST'&&u.pathname==='/execute'){
   const chunks=[];req.on('data',c=>chunks.push(c));req.on('end',()=>{
    const {id}=JSON.parse(Buffer.concat(chunks).toString());const job=input.jobs.find(j=>j.id===id);
    if(!job||serverJobs.has(id)){res.writeHead(400);res.end();return;}
    serverJobs.set(id,{state:'accepted'});record('server_accept',id);
    res.on('close',()=>record('server_connection_close',id,{ended:ended.has(id)}));
    later(()=>{serverJobs.get(id).state='running';active.add(id);record('effect_start',id);maxActive=Math.max(maxActive,active.size);
     if([...active].some(other=>other!==id&&conflict(id,other)))violation=true;
     later(()=>{active.delete(id);ended.add(id);serverJobs.get(id).state='done';record('effect_end',id);
      if(input.mode!=='accept_202'&&!res.destroyed){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({id,state:'done'}));record('server_response',id,{status:200});}
      inspect();
     },job.duration);
    },job.startDelay);
    if(input.mode==='accept_202')later(()=>{if(!res.destroyed){res.writeHead(202,{'Content-Type':'application/json'});res.end(JSON.stringify({id,state:'accepted'}));record('server_response',id,{status:202});}},12);
   });
  }else if(req.method==='GET'&&u.pathname==='/status'){
   const id=Number(u.searchParams.get('id'));const data=serverJobs.get(id);
   res.writeHead(data?200:404,{'Content-Type':'application/json'});res.end(JSON.stringify({id,state:data?.state||'unknown'}));
  }else{res.writeHead(404);res.end();}
 });
 let result;const timeout=later(()=>rejectCase(Error('Case exceeded 4 seconds')),4000);
 try{
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  const base=`http://127.0.0.1:${server.address().port}`;
  function register(RED){
   function Gate(c){RED.nodes.createNode(this,c);const node=this;
    function poll(id){
     if(!held.has(id)||settled)return;
     node.send([null,{kind:'status',jobId:id,url:`${base}/status?id=${id}`,requestTimeout:1000}]);
    }
    function pump(){
     for(let i=0;i<waiting.length;){
      const job=waiting[i];if([...held].some(other=>conflict(job.id,other))){i++;continue;}
      waiting.splice(i,1);held.add(job.id);dispatched.add(job.id);record('dispatch',job.id);
      node.send([{kind:'command',jobId:job.id,url:`${base}/execute`,payload:{id:job.id},requestTimeout:input.requestTimeout},null]);
      if(policy==='confirm_status')pollers.set(job.id,later(()=>poll(job.id),input.pollMs));
     }
    }
    node.on('input',(msg,send,doneInput)=>{
     try{
      if(msg.kind==='begin')pump();
      if(msg.kind==='command'){
       terminals.add(msg.jobId);record('http_terminal',msg.jobId,{status:msg.statusCode});
       const release=policy==='release_on_terminal'||(policy==='release_on_2xx'&&Number(msg.statusCode)>=200&&Number(msg.statusCode)<300);
       if(release){held.delete(msg.jobId);record('release',msg.jobId,{basis:'http_terminal'});pump();}
      }
      if(msg.kind==='status'){
       const data=msg.payload;record('status_observed',msg.jobId,{status:msg.statusCode,state:data?.state});
       if(msg.statusCode===200&&data?.id===msg.jobId&&data.state==='done'){
        held.delete(msg.jobId);record('release',msg.jobId,{basis:'status_done'});pump();
       }else pollers.set(msg.jobId,later(()=>poll(msg.jobId),input.pollMs));
      }
      inspect();doneInput();
     }catch(e){rejectCase(e);doneInput(e);}
    });
   }
   RED.nodes.registerType('http-contract-gate',Gate);
  }
  const flow=[{id:'gate',type:'http-contract-gate',wires:[['command'],['status']]},
   {id:'command',type:'http request',method:'POST',ret:'obj',senderr:false,url:'',wires:[['gate']]},
   {id:'status',type:'http request',method:'GET',ret:'obj',senderr:false,url:'',wires:[['gate']]}];
  await helper.load([httpNode,register],flow);gate=helper.getNode('gate');gate.receive({kind:'begin'});
  const status=await done;await new Promise(r=>setImmediate(r));
  result={input:input.id,policy,status,unsafe:violation,maxActive,dispatched:dispatched.size,ended:ended.size,waiting:waiting.length,heldAtEnd:held.size,
   httpErrors:trace.filter(t=>t.event==='http_terminal'&&typeof t.status!=='number').length,trace};
 }catch(error){result={input:input.id,policy,status:'error',error:error.stack,trace};}
 finally{settled=true;for(const t of timers)clearTimeout(t);timers.clear();await helper.unload();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
 return result;
}
async function main(){
 check();fs.mkdirSync(out,{recursive:false});
 helper.init(require.resolve('node-red'),{userDir:path.join(__dirname,'.runtime-http'),proxyOptions:{env:{http_proxy:'',https_proxy:'',all_proxy:'',no_proxy:'*'}},logging:{console:{level:'off'}}});
 const selectedIndex=args.indexOf('--input-id');
 const data=inputs().filter(input=>selectedIndex<0||input.id===args[selectedIndex+1]),result=[];
 if(!data.length)throw Error('No matching input for --input-id');
 save('inputs.json',data);
 const manifest={startedAt:new Date().toISOString(),node:process.version,nodeRed:require('node-red/package.json').version,httpNodeFile:path.relative(__dirname,httpFile).split(path.sep).join('/'),
  sourceSha256:sha(__filename),inputSha256:sha(path.join(out,'inputs.json')),httpNodeSha256:sha(httpFile),lockfileSha256:sha(path.join(__dirname,'package-lock.json')),
  execution:'official Node-RED HTTP Request node, official test helper, in-memory synthetic server at loopback ephemeral port; no external service'};
 save('manifest.json',manifest);
 for(const input of data)for(const policy of ['release_on_terminal','release_on_2xx','confirm_status']){
  check();const r=await run(input,policy);result.push(r);fs.appendFileSync(path.join(out,'results.jsonl'),JSON.stringify(r)+'\n');
 }
 save('results.json',result);const summary={inputs:data.length,conditions:result.length,policies:{}};
 for(const p of ['release_on_terminal','release_on_2xx','confirm_status']){
  const rs=result.filter(r=>r.policy===p);summary.policies[p]={complete:rs.filter(r=>r.status==='complete').length,stalled:rs.filter(r=>r.status==='stalled').length,
   errors:rs.filter(r=>r.status==='error').length,retainedReservations:rs.filter(r=>r.heldAtEnd>0).length,unsafe:rs.filter(r=>r.unsafe).length,maxObservedConcurrency:Math.max(0,...rs.map(r=>r.maxActive||0))};
 }
 manifest.finishedAt=new Date().toISOString();manifest.sourceUnchanged=manifest.sourceSha256===sha(__filename);manifest.inputUnchanged=manifest.inputSha256===sha(path.join(out,'inputs.json'));
 save('manifest.json',manifest);save('summary.json',summary);console.log(JSON.stringify(summary,null,2));
 if(result.some(r=>r.status==='error')||result.some(r=>r.policy==='confirm_status'&&(r.unsafe||r.status!=='complete')))process.exitCode=1;
}
main().catch(e=>{console.error(e);process.exitCode=1;});
