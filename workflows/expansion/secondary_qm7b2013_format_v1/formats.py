"""Passive member metadata. Never load numeric arrays or perceive a molecule."""
import hashlib,io,numbers,re,warnings
from pathlib import PurePosixPath
from . import contracts as C
from secondary_qm7b_official2013_acquisition_v1.archive import inventory
Q=C.Q

SYMBOLS=set(('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr '
    'Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu '
    'Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og').split())
NUMBER=re.compile(rb'[+-]?(?:(?:[0-9]+(?:\.[0-9]*)?)|(?:\.[0-9]+))(?:[EeDd][+-]?[0-9]+)?\Z')


class FormatUnknown(ValueError):pass


def need_format(ok,code):
    if not ok:raise FormatUnknown(code)


class MemberSink:
    """Bounded memory only; no second compressed or uncompressed file alias."""
    def __init__(self,maximum):
        self.maximum=maximum;self.current=bytearray();self.total=0;self.concat=hashlib.sha256()
    def write(self,raw):
        Q.need(self.total+len(raw)<=self.maximum and len(self.current)+len(raw)<=self.maximum,'ACTUAL_MEMBER_BUFFER_BOUND')
        self.current.extend(raw);self.total+=len(raw);self.concat.update(raw);return len(raw)
    def flush(self):pass
    def take(self):
        raw=bytes(self.current);self.current.clear();return raw


def lines(raw,emit):
    offset=0;count=0;column_counts={};blank=0
    for number,line in enumerate(raw.splitlines(keepends=True)):
        need_format(number<C.LINES and len(line)<=C.LINE_BYTES,'TEXT_LINE_OR_COUNT_BOUND_UNKNOWN')
        emit({'line_ordinal':number,'member_uncompressed_offset':offset,'bytes':len(line),
              'sha256':hashlib.sha256(line).hexdigest()})
        tokens=line.split();need_format(len(tokens)<=C.TOKENS,'TEXT_TOKEN_COUNT_BOUND_UNKNOWN')
        key=str(len(tokens));column_counts[key]=column_counts.get(key,0)+1
        blank+=not tokens;offset+=len(line);count+=1
    need_format(offset==len(raw),'FULL_LINE_BYTE_MASS_UNKNOWN')
    return {'physical_lines':count,'blank_lines':blank,'whitespace_column_count_histogram':column_counts,
            'headers_IDs_SMILES_or_numeric_values_accepted':False}


def xyz_metadata(raw):
    rows=raw.splitlines(keepends=True);cursor=0;records=0;atoms=0;symbols={};blanks=0
    while cursor<len(rows):
        if not rows[cursor].strip():cursor+=1;blanks+=1;continue
        token=rows[cursor].strip()
        need_format(re.fullmatch(rb'[0-9]{1,9}',token) is not None,'XYZ_ATOM_COUNT_HEADER_SYNTAX_UNKNOWN')
        n=int(token);need_format(0<n<=C.XYZ_ATOMS,'XYZ_STRUCTURAL_ATOM_COUNT_BOUND_UNKNOWN')
        need_format(cursor+2+n<=len(rows),'XYZ_INCOMPLETE_RECORD_UNKNOWN')
        # The comment/header is deliberately opaque; it may contain source IDs,
        # targets or SMILES. No text is returned and no row association is made.
        for line in rows[cursor+2:cursor+2+n]:
            tokens=line.split();need_format(len(tokens)==4,'XYZ_EXACT_SYMBOL_AND_THREE_LEXEMES_REQUIRED')
            try:symbol=tokens[0].decode('ascii')
            except UnicodeError:raise FormatUnknown('XYZ_SYMBOL_ENCODING_UNKNOWN')
            need_format(symbol in SYMBOLS and all(NUMBER.fullmatch(v) for v in tokens[1:]),
                        'XYZ_SYMBOL_OR_COORDINATE_LEXEME_UNKNOWN')
            symbols[symbol]=symbols.get(symbol,0)+1;atoms+=1
        records+=1;cursor+=2+n
    need_format(records>0,'XYZ_NO_COMPLETE_RECORDS_UNKNOWN')
    return {'format':'XYZ_LEXICAL_STRUCTURE_ONLY','records':records,'atomic_rows':atoms,
            'symbol_counts':symbols,'interrecord_blank_lines':blanks,
            'coordinate_floats_parsed':False,'comment_or_ID_parsed':False,'MAT_row_mapping':'UNKNOWN'}


def mat_metadata(raw):
    # The only MAT API is header metadata. No loadmat, object decoding, pickle,
    # reconstruction or coordinates/numeric array materialization is requested.
    import scipy
    from scipy.io import whosmat
    try:
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter('always');values=whosmat(io.BytesIO(raw),appendmat=False)
    except Exception as exc:
        return {'format':'MAT_METADATA_UNKNOWN_HOLD','reason':'WHOSMAT_'+type(exc).__name__,
                'scipy_version':scipy.__version__,'MAT_row_mapping':'UNKNOWN','array_values_loaded':False}
    need_format(len(values)<=C.MAT_FIELDS,'MAT_FIELD_COUNT_BOUND_UNKNOWN');output=[]
    for name,shape,kind in values:
        need_format(isinstance(name,str) and 0<len(name.encode('utf-8'))<=C.MAT_NAME_BYTES
            and isinstance(shape,tuple) and len(shape)<=C.MAT_DIMS
            and all(isinstance(v,numbers.Integral) and not isinstance(v,bool) and v>=0 for v in shape)
            and isinstance(kind,str) and len(kind)<=128,'BOUNDED_WHOSMAT_FIELD_METADATA_UNKNOWN')
        output.append({'field_name':name,'shape':[int(v) for v in shape],'MATLAB_class':kind})
    return {'format':'MAT_WHOSMAT_FIELD_METADATA_ONLY','fields':output,'scipy_version':scipy.__version__,
            'dtype_semantics':'whosmat MATLAB class, not loaded numpy array dtype',
            'array_values_loaded':False,'warning_types_only':[type(w.message).__name__ for w in observed],
            'MAT_row_mapping':'UNKNOWN'}


def inspect_member(name,raw,emit_line):
    suffix=PurePosixPath(name).suffix.lower()
    if suffix=='.mat' or raw.startswith(b'MATLAB '):
        try:return mat_metadata(raw)
        except FormatUnknown as exc:return {'format':'MAT_METADATA_UNKNOWN_HOLD','reason':str(exc),'MAT_row_mapping':'UNKNOWN','array_values_loaded':False}
    try:raw.decode('utf-8',errors='strict')
    except UnicodeError:
        return {'format':'UNKNOWN_BINARY_HOLD','reason':'NO_APPROVED_BINARY_PARSER','MAT_row_mapping':'UNKNOWN'}
    try:
        metadata=lines(raw,emit_line)
        if suffix=='.xyz':metadata.update(xyz_metadata(raw))
        elif suffix in ('.txt','.csv','.tsv','.dat') or 'readme' in PurePosixPath(name).name.lower():
            metadata.update(format='UTF8_OPAQUE_TEXT_LINE_COLUMN_METADATA',column_names_accepted=False,
                            first_line_or_number_is_MAT_rowmap=False,MAT_row_mapping='UNKNOWN')
        else:metadata.update(format='UNKNOWN_UTF8_FORMAT_HOLD',reason='NO_APPROVED_RECORD_PARSER',MAT_row_mapping='UNKNOWN')
        return metadata
    except FormatUnknown as exc:
        return {'format':'FORMAT_BOUNDARY_UNKNOWN_HOLD','reason':str(exc),'MAT_row_mapping':'UNKNOWN'}
