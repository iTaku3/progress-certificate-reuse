#!/usr/bin/env python3
"""Reference interface selection in finite one-shot asynchronous jobs.

No novelty claim: compares a known combinatorial cover with an explicit
adversarial completion game under the assumptions in the protocol.
"""
import argparse,hashlib,itertools,json,platform,random,time
from datetime import datetime,timezone
from functools import lru_cache
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DEADLINE=datetime.fromisoformat('2026-09-08T11:00:00+09:00').timestamp()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def make_inputs():
    data=[dict(id='one_conflict',n=2,edges=[[0,1]],costs=[2,1]),dict(id='triple_only',n=3,edges=[[0,1,2]],costs=[3,2,1]),dict(id='triangle',n=3,edges=[[0,1],[1,2],[0,2]],costs=[3,2,1]),dict(id='empty_five',n=5,edges=[],costs=[2,3,1,4,5])]
    for n in range(3,10):
        for seed in range(8):
            rng=random.Random(10000+n*100+seed)
            edges=[list(e) for k in range(2,min(4,n)+1) for e in itertools.combinations(range(n),k) if rng.random()<(.025+.035*seed)]
            data.append(dict(id=f'n{n}_s{seed}',n=n,edges=edges,costs=[rng.randint(1,7) for _ in range(n)]))
    return data

def solve_game(n,edge_masks,observed):
    full=(1<<n)-1;policy={}
    @lru_cache(None)
    def win(started,finished):
        active=started&~finished
        if any(active&edge==edge for edge in edge_masks):return False
        if started==full:return True
        for j in range(n):
            bit=1<<j
            if not started&bit and win(started|bit,finished):
                policy[(started,finished)]=('start',j);return True
        candidates=[1<<j for j in range(n) if active&observed&(1<<j)]
        if candidates and all(win(started,finished|bit) for bit in candidates):
            policy[(started,finished)]=('wait',None);return True
        return False
    result=win(0,0);visited=win.cache_info().currsize
    verified=0;error=None
    if result:
        stack=[(0,0)];seen=set()
        while stack:
            state=stack.pop()
            if state in seen:continue
            seen.add(state);started,finished=state;active=started&~finished
            if any(active&edge==edge for edge in edge_masks):error='unsafe policy state';break
            if started==full:continue
            action=policy.get(state)
            if action is None:error='missing policy';break
            if action[0]=='start':
                bit=1<<action[1]
                if started&bit:error='repeated start';break
                stack.append((started|bit,finished))
            else:
                outcomes=[(started,finished|(1<<j)) for j in range(n) if active&observed&(1<<j)]
                if not outcomes:error='wait without observable completion';break
                stack.extend(outcomes)
        verified=len(seen)
    return result,visited,verified,error

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'outputs/interface-selection');p.add_argument('--enforce-deadline',action='store_true');a=p.parse_args()
    def check():
        if a.enforce_deadline and time.time()>=DEADLINE:raise RuntimeError('research deadline reached')
    check();out=a.output.resolve();out.mkdir(exist_ok=False);data=make_inputs();save(out/'inputs.json',data)
    manifest=dict(started_at=datetime.now(timezone.utc).isoformat(),python=platform.python_version(),platform=platform.platform(),source_sha256=digest(Path(__file__)),input_sha256=digest(out/'inputs.json'),semantics='finite one-shot jobs; reliable chosen completion observations; independent finite unbounded durations; fairness abstracted by completion wait')
    save(out/'manifest.json',manifest);summaries=[];conditions=0;mismatches=[];invalid=[]
    with (out/'conditions.jsonl').open('w') as log:
        for inp in data:
            check();n=inp['n'];edges=[sum(1<<j for j in e) for e in inp['edges']];rows=[];begin=time.perf_counter()
            for observed in range(1<<n):
                check();cover=all(observed&edge for edge in edges);t=time.perf_counter();game,states,verified,error=solve_game(n,edges,observed)
                row=dict(input=inp['id'],observed=[j for j in range(n) if observed&(1<<j)],cost=sum(c for j,c in enumerate(inp['costs']) if observed&(1<<j)),cover=bool(cover),game=game,visited_states=states,policy_verified_states=verified,policy_error=error,seconds=time.perf_counter()-t)
                log.write(json.dumps(row)+'\n');rows.append(row);conditions+=1
                if bool(cover)!=game:mismatches.append(row)
                if error:invalid.append(row)
            feasible=[row for row in rows if row['game']];opt=min((row['cost'] for row in feasible),default=None)
            summary=dict(id=inp['id'],n=n,edges=len(edges),conditions=len(rows),feasible=len(feasible),min_cost=opt,minimum_cost_observations=[row['observed'] for row in feasible if row['cost']==opt],visited_states=sum(row['visited_states'] for row in rows),policy_verified_states=sum(row['policy_verified_states'] for row in rows),seconds=time.perf_counter()-begin)
            summaries.append(summary);save(out/'cases.json',summaries);print(json.dumps(summary),flush=True)
    manifest['finished_at']=datetime.now(timezone.utc).isoformat();manifest['source_unchanged']=digest(Path(__file__))==manifest['source_sha256'];manifest['input_unchanged']=digest(out/'inputs.json')==manifest['input_sha256'];save(out/'manifest.json',manifest)
    distinct=len({json.dumps({k:x[k] for k in ['n','edges','costs']},sort_keys=True) for x in data})
    summary=dict(inputs=len(data),distinct_inputs=distinct,conditions=conditions,mismatches=len(mismatches),invalid_policies=len(invalid),feasible_conditions=sum(s['feasible'] for s in summaries),visited_states=sum(s['visited_states'] for s in summaries),policy_verified_states=sum(s['policy_verified_states'] for s in summaries),total_solver_seconds=sum(s['seconds'] for s in summaries))
    save(out/'summary.json',summary);save(out/'mismatches.json',mismatches);save(out/'invalid_policies.json',invalid);print(json.dumps(summary,indent=2));return int(bool(mismatches or invalid))
if __name__=='__main__':raise SystemExit(main())
