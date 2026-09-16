#!/usr/bin/env python3
"""Independent offline check of Node-RED HTTP experiment event records."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('results');p.add_argument('--source',type=Path,help='archived HTTP experiment source to verify instead of the current source');a=p.parse_args();out=Path(a.results).resolve()
inputs={x['id']:x for x in json.loads((out/'inputs.json').read_text())}
rows=json.loads((out/'results.json').read_text());errors=[];by_mode={};checked=0
for row in rows:
    inp=inputs[row['input']];edges={frozenset(e) for e in inp['graph']['edges']}
    active=set();dispatched=set();accepted=set();ended=set();terminal=set();held=set();unsafe=False;peak=0;err=[]
    for index,event in enumerate(row['trace']):
        e=event['event'];j=event.get('id')
        if event['index']!=index:err.append('nonsequential record index')
        if e=='dispatch':
            if j in dispatched:err.append('duplicate dispatch')
            dispatched.add(j);held.add(j)
        elif e=='server_accept':
            if j not in dispatched or j in accepted:err.append('invalid server accept')
            accepted.add(j)
        elif e=='effect_start':
            if j not in accepted or j in active or j in ended:err.append('invalid effect start')
            active.add(j);peak=max(peak,len(active))
            if any(edge<=active for edge in edges):unsafe=True
        elif e=='effect_end':
            if j not in active or j in ended:err.append('invalid effect end')
            active.discard(j);ended.add(j)
        elif e=='http_terminal':
            if j in terminal:err.append('duplicate terminal')
            terminal.add(j)
        elif e=='status_observed' and event.get('state')=='done':
            if j not in ended:err.append('status says done before effect end')
        elif e=='release':
            if j not in held:err.append('release without reservation')
            held.discard(j)
            if event.get('basis')=='status_done' and j not in ended:err.append('confirmed release before effect end')
    n=inp['graph']['n'];waiting=n-len(dispatched)
    if row['status']!='error':
        for name,actual in [('unsafe',unsafe),('maxActive',peak),('dispatched',len(dispatched)),('ended',len(ended)),('waiting',waiting),('heldAtEnd',len(held))]:
            if row.get(name)!=actual:err.append(f'{name}: recorded={row.get(name)} replay={actual}')
        if row['status']=='complete' and (len(ended)!=n or len(terminal)!=n or waiting):err.append('incomplete job set marked complete')
        if row['status']=='stalled' and not (waiting>0 and ended==dispatched and terminal==dispatched and held):err.append('stalled without evidence')
        if row['policy']=='confirm_status' and row['status']=='complete' and held:err.append('final observations missing')
    key=f"{inp['mode']}|{row['policy']}";s=by_mode.setdefault(key,dict(conditions=0,unsafe=0,complete=0,stalled=0,error=0,heldAtEndConditions=0))
    s['conditions']+=1;s['unsafe']+=int(unsafe);s[row['status']]+=1;s['heldAtEndConditions']+=int(bool(held))
    if err:errors.append({'input':row['input'],'policy':row['policy'],'errors':err})
    checked+=1
manifest=json.loads((out/'manifest.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
lab=Path(__file__).resolve().parent
source=a.source.resolve() if a.source else lab/'http_experiment.cjs'
http_node=lab/'node_modules/@node-red/nodes/core/network/21-httprequest.js'
hashes={'input':sha(out/'inputs.json')==manifest['inputSha256'],'recorded_source':sha(source)==manifest['sourceSha256'],'lockfile':sha(lab/'package-lock.json')==manifest['lockfileSha256'],'http_node':sha(http_node)==manifest['httpNodeSha256']}
report={'conditions':checked,'mismatches':len(errors),'errors':errors,'hash_verification':hashes,'by_mode':by_mode,'replay_source_sha256':sha(Path(__file__))}
(out/'independent_replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(int(bool(errors) or not all(hashes.values())))
