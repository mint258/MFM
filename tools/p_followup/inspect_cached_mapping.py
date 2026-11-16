import pickle
from resources import OLD
for name in ['current_graph_identities_TRAIN.pkl']:
    with (OLD/name).open('rb') as stream:a=pickle.load(stream)
    print(name,type(a),len(a))
    for k,v in list(a.items())[:2]:
        print(k,type(v),len(v))
        if isinstance(v,dict):print('first',list(v.items())[:1])
        else:print('first',list(v)[:1])