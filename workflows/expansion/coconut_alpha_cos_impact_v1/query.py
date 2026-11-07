"""One column, JSON-array semantics, and a complete counted SQL scan."""
X=(1,5,6,7,8,9,14,15,16,17,34,35,53)


def query(relation):
    if relation not in ('candidates','fixture'):raise ValueError('Explicit relation required')
    return '''WITH parsed AS (
      SELECT non_h_composition AS text,try_cast(non_h_composition AS BIGINT[][]) AS v FROM '''+relation+'''
    ), checked AS (
      SELECT v,coalesce(v IS NOT NULL AND to_json(v)::VARCHAR=text
        AND NOT coalesce(list_bool_or(list_transform(v,p -> p IS NULL OR len(p)<>2
          OR p[1] IS NULL OR p[1]<2 OR p[1]>118 OR p[2] IS NULL OR p[2]<=0)),false)
        AND list_transform(v,p -> p[1])=list_sort(list_distinct(list_transform(v,p -> p[1]))),false) AS valid
      FROM parsed
    ), flags AS (
      SELECT valid,coalesce(list_contains(list_transform(v,p -> p[1]),6),false) AS c,
        coalesce(list_contains(list_transform(v,p -> p[1]),8),false) AS o,
        coalesce(list_contains(list_transform(v,p -> p[1]),16),false) AS s,
        coalesce(len(v)=0,false) AS empty_non_H,
        coalesce(list_contains(list_transform(v,p -> p[1]),26),false) AS fe,
        coalesce(list_bool_or(list_transform(v,p -> p[1] NOT IN ('''+','.join(map(str,X))+'''))),false) AS outside_X
      FROM checked
    ) SELECT valid,c,o,s,empty_non_H,fe,outside_X,count(*) AS rows
      FROM flags GROUP BY ALL ORDER BY ALL'''


def census(db,relation):
    result=db.execute(query(relation))
    names=[column[0] for column in result.description]
    return [dict(zip(names,row)) for row in result.fetchall()]


def summarize(groups):
    total=sum(r['rows'] for r in groups);valid=[r for r in groups if r['valid']]
    combos=[]
    for c in (False,True):
        for o in (False,True):
            for s in (False,True):
                combos.append(dict(C=c,O=o,S=s,rows=sum(r['rows'] for r in valid if (r['c'],r['o'],r['s'])==(c,o,s))))
    hit=sum(r['rows'] for r in valid if r['c'] or r['o'] or r['s'])
    none=sum(r['rows'] for r in valid if not (r['c'] or r['o'] or r['s']))
    invalid=total-sum(r['rows'] for r in valid)
    return dict(total_rows=total,valid_canonical_composition_rows=total-invalid,
        invalid_or_noncanonical_composition_rows=invalid,contains_any_C_O_S=hit,contains_none_C_O_S=none,
        empty_non_H_vector_rows=sum(r['rows'] for r in valid if r['empty_non_H']),
        Fe_containing_rows=sum(r['rows'] for r in valid if r['fe']),
        outside_original_X_element_rows=sum(r['rows'] for r in valid if r['outside_X']),
        eight_C_O_S_combinations=combos,grouped_diagnostic_counts=groups,
        all_rows_accounted=total==hit+none+invalid)
