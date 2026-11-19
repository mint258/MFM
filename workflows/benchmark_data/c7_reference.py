"""Stream original C7 reference geometries and both thermochemical property sets."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tarfile
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem
from .admission import protect
from .domain import assess
from .build_csv_domain import SCHEMA as DOMAIN_SCHEMA

THERMO={'ZPVE':11,'U0':12,'U298':13,'H298':14,'G298':15}


def number(value):return float(value.replace('*^','e'))


def parse_xyz(text):
    lines=text.splitlines();n=int(lines[0]);header=lines[1].split()
    if len(header)!=17:raise ValueError('QM9 property header differs from author documentation')
    atoms=[line.split() for line in lines[2:2+n]]
    if len(atoms)!=n or any(len(row)<4 for row in atoms):raise ValueError('Incomplete author XYZ')
    smiles=lines[n+3].split()
    if len(smiles)!=2:raise ValueError('Missing original and relaxed geometry SMILES')
    return {'gdb9_index':int(header[1]),'header_lexemes':header,
        'atomic_numbers':[Chem.GetPeriodicTable().GetAtomicNumber(row[0]) for row in atoms],
        'coordinates_A':[[number(x) for x in row[1:4]] for row in atoms],
        'original_smiles':smiles[0],'relaxed_smiles':smiles[1]}


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--attempt',required=True);p.add_argument('--quota-snapshot',type=Path,required=True)
    a=p.parse_args();root=a.root
    protect(root,268435456,a.quota_snapshot)
    out=root/'reference/C7H10O2'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    source=root/'raw/C7H10O2/dsC7O2H10nsd.xyz.tar.bz2'
    companion=root/'raw/C7H10O2_B3LYP_companion/dsgdb9nsd.xyz.tar.bz2'
    molecules={}
    with tarfile.open(source,mode='r|bz2') as archive:
        for member_ordinal,member in enumerate(archive):
            if not member.isfile():continue
            value=parse_xyz(archive.extractfile(member).read().decode())
            key=value['gdb9_index']
            if key in molecules:raise ValueError('Duplicate original C7 record ID')
            molecules[key]=dict(value,source_member=member.name,source_member_ordinal=member_ordinal)
    paired={}
    with tarfile.open(companion,mode='r|bz2') as archive:
        for member in archive:
            if not member.isfile():continue
            stream=archive.extractfile(member);stream.readline();header=stream.readline().decode().split()
            key=int(header[1])
            if key in molecules:
                if key in paired:raise ValueError('Duplicate original B3LYP ID')
                paired[key]=header
    if set(molecules)!=set(paired):raise ValueError('Original C7 and B3LYP record IDs do not close')
    reference_schema=pa.schema([('record_id',pa.string()),('gdb9_index',pa.int64()),('source_member',pa.string()),
        ('source_member_ordinal',pa.int64()),
        ('source_atom_indices',pa.list_(pa.int32())),('atomic_numbers',pa.list_(pa.int16())),
        ('coordinates_A',pa.list_(pa.list_(pa.float64(),3))),('relaxed_smiles',pa.string()),
        ('G4MP2_property_lexemes',pa.list_(pa.string())),('B3LYP_property_lexemes',pa.list_(pa.string())),
        ('paired_thermochemistry_hartree_json',pa.string()),('domain_eligible',pa.bool_())])
    buffer=[];domains=[];reasons=Counter();primary=Counter();eligible=0
    with pq.ParquetWriter(out/'reference.parquet',reference_schema,compression='zstd') as writer, \
         pq.ParquetWriter(out/'all_rows.parquet',DOMAIN_SCHEMA,compression='zstd') as domain_writer:
        def flush():
            if buffer:
                protect(root,268435456,a.quota_snapshot)
                writer.write_table(pa.Table.from_pylist(buffer,schema=reference_schema));buffer.clear()
                domain_writer.write_table(pa.Table.from_pylist(domains,schema=DOMAIN_SCHEMA));domains.clear()
        for index,(key,row) in enumerate(sorted(molecules.items())):
            rid='C7H10O2:gdb9:'+str(key);domain=assess(row['relaxed_smiles'])
            eligible+=domain['domain_eligible'];reasons.update(domain['reasons'])
            if domain['reasons']:primary[domain['reasons'][0]]+=1
            properties={}
            for name,column in THERMO.items():
                g4=number(row['header_lexemes'][column]);b3=number(paired[key][column])
                properties[name]={'G4MP2':g4,'B3LYP':b3,'delta_G4MP2_minus_B3LYP':g4-b3}
            buffer.append({'record_id':rid,'gdb9_index':key,'source_member':row['source_member'],
                'source_member_ordinal':row['source_member_ordinal'],
                'source_atom_indices':list(range(len(row['atomic_numbers']))),
                'atomic_numbers':row['atomic_numbers'],'coordinates_A':row['coordinates_A'],
                'relaxed_smiles':row['relaxed_smiles'],'G4MP2_property_lexemes':row['header_lexemes'],
                'B3LYP_property_lexemes':paired[key],'paired_thermochemistry_hartree_json':json.dumps(properties),
                'domain_eligible':domain['domain_eligible']})
            domains.append({'dataset':'C7H10O2','source_file':row['source_member'],'source_row':0,
                'record_id':rid,'original_smiles':row['relaxed_smiles'],'model_smiles':domain['model_smiles'],
                'model_atom_to_source':domain['model_atom_to_source'],'heavy_atoms':domain['heavy_atoms'],
                'charge':domain['charge'],'salt_removed':False,'domain_eligible':domain['domain_eligible'],
                'retained':domain['retained'],'blind_fallback_required':False,'exclusion_reasons':domain['reasons'],
                'official_split':None,'original_fields_json':json.dumps({'original_smiles':row['original_smiles'],
                'gdb9_index':key,'G4MP2_property_lexemes':row['header_lexemes'],'B3LYP_property_lexemes':paired[key]})})
            if len(buffer)>=256:flush()
        flush()
    report={'status':'REFERENCE_AND_DOMAIN_READY_ENERGY_TARGET_BINDING_PENDING','dataset':'C7H10O2',
        'source':str(source),'companion':str(companion),'records':str(out/'all_rows.parquet'),
        'reference_geometries':str(out/'reference.parquet'),
        'counts':[{'before':len(molecules),'domain_eligible':eligible,'retained':eligible,
            'reason_counts_nonexclusive':dict(reasons),'primary_reason_counts':dict(primary)}],
        'geometry_source':'Original B3LYP reference XYZ in G4MP2 archive; never regenerated',
        'coordinate_precision':'Original parsed F64, source XYZ atom order',
        'reference_atom_to_model_smiles_mapping':'NOT_ASSUMED; original XYZ and SMILES orders both retained',
        'thermochemical_properties_retained':list(THERMO),'property_units':'Hartree',
        'benchmark_energy_column':'PENDING primary energy definition binding; no outcome-based selection',
        'no_new_benchmark_tasks_defined':True,'individual_XYZ_files_extracted':False,
        'independent_numeric_readback':False,'P_D_ready':False}
    protect(root,1048576,a.quota_snapshot)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('C7_REFERENCE_DOMAIN_CLOSED',len(molecules),eligible,out,flush=True)

if __name__=='__main__':main()
