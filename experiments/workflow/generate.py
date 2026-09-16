"""Historical Workflow transformation; input is fetched separately."""

def replace_once(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b)

def source(model_path, n):
    raw=model_path.read_text();s='\n'.join(raw.splitlines()[:154])+'\n'
    extra=[f'Check{i}' for i in range(n-2)]
    if not extra:return s
    s=replace_once(s,'set ControllableActions = {initInventory, initCredit, eval, initShipping, initBilling, archive, rollback}',
        'set ControllableActions = {initInventory, initCredit, eval, initShipping, initBilling, archive, rollback, '+', '.join('init'+j for j in extra)+'}')
    s=replace_once(s,'set FirstStep = {initInventory,endInventory,initCredit,endCredit}',
        'set FirstStep = {initInventory,endInventory,initCredit,endCredit,'+','.join(e+j for j in extra for e in ['init','end'])+'}')
    s=replace_once(s,'set All = {ControllableActions, orderEntry, approve, reject, endInventory, endCredit, endShipping, endBilling}',
        'set All = {ControllableActions, orderEntry, approve, reject, endInventory, endCredit, endShipping, endBilling, '+', '.join('end'+j for j in extra)+'}')
    defs='\n'.join(f'{j.upper()}_{v} = (init{j} -> AT_{j.upper()}_{v}),\nAT_{j.upper()}_{v} = (end{j} -> {j.upper()}_{v}).' for j in extra for v in ['OLD','NEW'])
    s=replace_once(s,'relation R_ENTRY =',defs+'\n\nrelation R_ENTRY =')
    for v,title in [('OLD','Old'),('NEW','New')]:
        old=f'||{title}Env = (ENTRY_{v} || INVENTORY_{v} || CREDIT_{v} || SHIPPING_{v} || BILLING_{v}).'
        new=old[:-2]+' || '+' || '.join(f'{j.upper()}_{v}' for j in extra)+').'
        s=replace_once(s,old,new)
    fluents='\n'.join(f'fluent {j}Finished = <end{j},{{orderEntry}}>\nfluent {j}Initiated = <init{j},{{orderEntry}}>' for j in extra)
    s=replace_once(s,'//Fluents declaration','//Fluents declaration\n'+fluents)
    s=replace_once(s,'assert EVAL_POLICY = (eval-> (InventoryFinished && CreditFinished))',
        'assert EVAL_POLICY = (eval-> (InventoryFinished && CreditFinished && '+' && '.join(j+'Finished' for j in extra)+'))')
    s=replace_once(s,'(initShipping -> OrderApproved) && (initBilling -> OrderApproved))',
        '(initShipping -> OrderApproved) && (initBilling -> OrderApproved) && '+' && '.join(f'(init{j} -> OrderArrived)' for j in extra)+')')
    s=replace_once(s,'(ShippingFinished -> !initShipping) && (BillingFinished -> !initBilling) )',
        '(ShippingFinished -> !initShipping) && (BillingFinished -> !initBilling) && '+' && '.join(f'({j}Finished -> !init{j})' for j in extra)+' )')
    return s
