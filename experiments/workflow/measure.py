"""Predeclared limited record-reconstruction benchmark, not update synthesis."""
from pathlib import Path
import sys,time,json,hashlib,statistics
from collections import deque
HERE=Path(__file__).resolve().parent
from support import read_aut, CONTROLLABLE, base, canonical, merge, compose


def episode(path,n):
    jobs=['Inventory','Credit']+[f'Check{i}' for i in range(n-2)]+['Shipping','Billing']
    all_bits=(1<<len(jobs))-1;initial,edges=read_aut(path)
    entries=[w for e,w in edges[initial] if e=='orderEntry'];assert len(entries)==1
    start=entries[0];states={start:('first',0,0,1,0)};todo=deque([start]);labelled=[]
    while todo:
        v=todo.popleft();phase,initiated,finished,accepted,approved=states[v]
        if phase.startswith('done_'):
            labelled.append((v,'episode_done',v));continue
        for event,w in edges[v]:
            pp,ii,ff,aa,rr=phase,initiated,finished,accepted,approved
            if event.startswith('init'):ii|=1<<jobs.index(event[4:])
            elif event.startswith('end'):ff|=1<<jobs.index(event[3:])
            elif event=='eval':pp='decision'
            elif event=='approve':pp,rr='second',1
            elif event in ('reject','archive'):pp,aa='done_'+event,0
            else:raise ValueError(event)
            new=pp,ii,ff,aa,rr
            if w in states:assert states[w]==new,(w,states[w],new)
            else:states[w]=new;todo.append(w)
            labelled.append((v,event,w))
    names={v:':'.join(map(str,s)) for v,s in states.items()};assert len(set(names.values()))==len(names)
    typed={names[v]:s for v,s in states.items()};graph={v:set() for v in typed}
    for s,e,t in labelled:graph[names[s]].add(names[t])
    groups={v:'A' if s[0] in ('first','decision') else 'B' if s[0]=='second' else 'T' for v,s in typed.items()}
    cons=[(names[s],names[t]) for s,e,t in labelled if groups[names[s]]!=groups[names[t]]]
    colors={v:all_bits^(s[1]&~s[2]&all_bits) for v,s in typed.items()}
    goals={v for v,s in typed.items() if s[0].startswith('done_')};ports={names[start]}|goals|{v for edge in cons for v in edge}
    fragments=[]
    for part in ('A','B','T'):
        vs={v for v,p in groups.items() if p==part}
        fragments.append(base.Fragment(part,{v:graph[v]&vs for v in vs},ports&vs,{v:colors[v] for v in vs},set(),goals&vs))
    cross=[(names[s],e,names[t]) for s,e,t in labelled if groups[names[s]]!=groups[names[t]]]
    assert not [e for s,e,t in cross if e.startswith('end')]
    for v,s in typed.items():
        pending=s[1]&~s[2]&all_bits
        assert not (pending>>n) if groups[v]=='A' else True
        assert not (pending&((1<<n)-1)) if groups[v]=='B' else True
        assert not pending if groups[v]=='T' else True
    stats={'episode_states':len(graph),'native_states':len(edges),'states_by_group':{f.name:len(f.graph) for f in fragments},
           'ports_by_group':{f.name:len(f.ports) for f in fragments},'max_pending':max((s[1]&~s[2]&all_bits).bit_count() for s in states.values()),
           'uncontrollable_cross_events':[e for s,e,t in cross if e not in CONTROLLABLE],
           'asynchronous_responses_stay_in_stage':True,'all_cross_edges':cross}
    return fragments,cons,names[start],goals,all_bits,stats


def pair(fragment,bits):return tuple(base.local_summary(fragment,bits,avoid) for avoid in (False,True))

def check(records,cons,start,goals,bits):
    combined=[]
    for i in (0,1):
        ports=set().union(*(set(p[i]['ports']) for p in records))
        combined.append(compose([p[i] for p in records],[(s,t) for s,t in cons if s in ports and t in ports],({start}|goals)&ports,bits))
    return combined,base.summary_check([combined[0]],[combined[1]],[],start,bits)

def record_items(records):
    return {'path_items':sum(len(p[i]['edges']) for p in records for i in (0,1)),
            'exit_sets':sum(sum(len(v) for v in p[i]['exit_signatures'].values()) for p in records for i in (0,1)),
            'json_bytes':sum(len(canonical(p[i]).encode()) for p in records for i in (0,1)),
            'path_product_visits':sum(p[i]['product_visits'] for p in records for i in (0,1))}

def measure(n, input_root, output_root):
    folder=Path(input_root)/f'n{n}';old,_,_,_,bits,old_stat=episode(folder/'old.aut',n)
    new,cons,start,goals,bits,new_stat=episode(folder/'new.aut',n)
    t=time.perf_counter_ns();old_records=[pair(f,bits) for f in old];old_initial_ms=(time.perf_counter_ns()-t)/1e6
    full=merge(new,cons,{start}|goals)
    direct=base.full_oracle(full.graph,full.colors,full.goal,full.unsafe,start,bits);assert all(direct.values())
    all_records=[pair(f,bits) for f in new]
    assert all(canonical(a)==canonical(b) for idx in (0,2) for a,b in zip(old_records[idx],all_records[idx]))
    whole,verdict=check(all_records,cons,start,goals,bits);assert verdict==direct
    for i in (0,1):assert canonical(whole[i])==canonical(base.local_summary(full,bits,bool(i)))
    archive=next(v for v in goals if v.startswith('done_archive:'))
    _,negative=check(all_records,[(s,t) for s,t in cons if t!=archive],start,goals,bits)
    assert not negative['nonconflicting']
    samples={'full':[],'reuse':[]}
    def run(method):
        t0=time.perf_counter_ns()
        if method=='full':records=[pair(f,bits) for f in new]
        else:records=[old_records[0],pair(new[1],bits),old_records[2]]
        t1=time.perf_counter_ns();joined,ok=check(records,cons,start,goals,bits);t2=time.perf_counter_ns()
        assert ok==direct and all(canonical(a)==canonical(b) for a,b in zip(joined,whole))
        return {'record_ms':(t1-t0)/1e6,'boundary_and_check_ms':(t2-t1)/1e6,'total_ms':(t2-t0)/1e6}
    run('full');run('reuse')
    for rep in range(7):
        for method in (['full','reuse'] if rep%2==0 else ['reuse','full']):samples[method].append(run(method))
    summary={method:{key:{'median':statistics.median(x[key] for x in rows),'min':min(x[key] for x in rows),'max':max(x[key] for x in rows)} for key in rows[0]} for method,rows in samples.items()}
    result={'n':n,'old_structure':old_stat,'new_structure':new_stat,'old_initial_record_ms':old_initial_ms,
            'old_record_items':record_items(old_records),'new_record_items':record_items(all_records),
            'recreated_record_path_product_visits':record_items([all_records[1]])['path_product_visits'],
            'full_rebuild_input_states':sum(len(f.graph) for f in new),'reuse_rebuild_input_states':len(new[1].graph),
            'all_boundary_ports_checked':sum(len(f.ports) for f in new),'boundary_product_visits':sum(r['product_visits'] for r in whole),
            'three_guarantees':direct,'full_record_equality':True,'negative_archive_connector':negative,'samples':samples,'timing_summary':summary}
    output_folder=Path(output_root)/f'n{n}'
    output_folder.mkdir(parents=True,exist_ok=True)
    (output_folder/'record_measurement.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(n,new_stat['episode_states'],summary['full']['total_ms']['median'],summary['reuse']['total_ms']['median'],flush=True)
    return result

