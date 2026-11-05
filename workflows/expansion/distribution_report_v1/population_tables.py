"""Export the original counted population statistics without claiming comparisons."""
import json
from .aggregate import Moments
from .functional_groups import FUNCTIONS
from .io import canonical,export_cursor,need,write_new
from .render import export_all_counts,long_tail


def export(db,out):
    groups=tuple(name for name, in db.execute('SELECT name FROM populations WHERE complete=1 ORDER BY name'))
    need(groups,'At least one physically complete declared population is required')
    totals=dict(db.execute('SELECT name,expected FROM populations WHERE complete=1'))
    numeric=[];histogram=[]
    for group,field,raw in db.execute('SELECT population,field,state FROM moments ORDER BY population,field'):
        if group not in groups:continue
        value=Moments(field,json.loads(raw))
        numeric.append((group,field,*value.summary()))
        histogram.extend((group,field,*row) for row in value.histogram())
    refs=[export_cursor(out/'numeric_summary.csv',['population','field','n','mean','population_std','min','max'],numeric),
        export_cursor(out/'fixed_histograms_and_bin_ecdf.csv',
            ['population','field','bin','left','right','count','cumulative_count','bin_ecdf'],histogram),
        export_all_counts(db,out/'complete_categorical_counts.parquet',groups)]
    fg=[]
    for group in groups:
        counts={(kind,key):n for kind,key,n in db.execute(
            "SELECT kind,key,n FROM counts WHERE population=? AND kind IN ('functional_prevalence','functional_matches')",(group,))}
        for function in FUNCTIONS:
            prevalent,matches=counts.get(('functional_prevalence',function),0),counts.get(('functional_matches',function),0)
            fg.append((group,function,prevalent,matches,prevalent/totals[group],matches/totals[group]))
    refs.append(export_cursor(out/'functional_groups.csv',
        ['population','definition','molecules_present','total_unique_matches','prevalence','mean_matches'],fg))
    refs.append(export_cursor(out/'scaffold_frequency_spectrum.csv',
        ['population','molecules_per_scaffold','number_of_scaffolds','molecules'],
        (row for row in db.execute("SELECT population,n,count(*),n*count(*) FROM counts WHERE kind='scaffold' GROUP BY population,n ORDER BY population,n") if row[0] in groups)))
    refs.append(write_new(out/'population_summary.json',{
        'schema':'EXPANSION_POPULATION_ONLY_COUNTED_SUMMARY_V1','status':'DECLARED_POPULATIONS_COMPLETE',
        'populations':totals,'scaffold_long_tail':{group:long_tail(db,group,totals[group]) for group in groups},
        'histograms_use_unchanged_original_Moments':True,'functional_group_definitions_overlap':True,
        'bin_ecdf_is_fixed_bin_not_an_unbinned_curve':True,'Common_or_exact_nearest_comparison_claimed':False}))
    return refs,groups
