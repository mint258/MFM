"""Pure byte counters, independent of the frozen CSV parser and all text values."""
from collections import Counter

class ByteCensus:
    PATTERNS={'CRLF':b'\r\n','CRCRLF':b'\r\r\n'}
    def __init__(self):
        self.total=0;self.tail=b'';self.counts=Counter(CR=0,LF=0,CRLF=0,CRCRLF=0)
        self.examples={key:[] for key in self.PATTERNS};self.lines=Counter();self.pending_CR=None
        self.line_start=0;self.body=0;self.only_horizontal=True;self.maximum_body=0;self.line_examples=[];self.closed=False
    def close_line(self,end,terminator):
        self.lines['physical_lines_including_header']+=1;self.lines['terminator:'+terminator]+=1
        empty=self.body==0;self.lines['literal_empty_lines']+=empty
        self.lines['nonempty_ASCII_space_or_tab_only_lines']+=bool(self.body and self.only_horizontal)
        self.maximum_body=max(self.maximum_body,self.body)
        if empty and len(self.line_examples)<4:self.line_examples.append({'line_ordinal':self.lines['physical_lines_including_header'],
            'offset':self.line_start,'bytes':end-self.line_start,'terminator':terminator,'contains_source_values':False})
        self.line_start=end;self.body=0;self.only_horizontal=True
    def feed(self,data):
        if self.closed:raise ValueError('NO_BYTES_AFTER_EOF')
        combined=self.tail+data;base=self.total-len(self.tail)
        self.counts['CR']+=data.count(b'\r');self.counts['LF']+=data.count(b'\n')
        for name,pattern in self.PATTERNS.items():
            self.counts[name]+=combined.count(pattern)-self.tail.count(pattern)
            start=0
            while len(self.examples[name])<4:
                position=combined.find(pattern,start)
                if position<0:break
                if position+len(pattern)>len(self.tail):self.examples[name].append(base+position)
                start=position+1
        for value in data:
            offset=self.total;self.total+=1
            if self.pending_CR is not None:
                old=self.pending_CR;self.pending_CR=None
                if value==10:self.close_line(offset+1,'CRLF');continue
                self.close_line(old+1,'CR')
            if value==13:self.pending_CR=offset
            elif value==10:self.close_line(offset+1,'LF')
            else:self.body+=1;self.only_horizontal=self.only_horizontal and value in (9,32)
        self.tail=combined[-2:]
    def finish(self):
        if not self.closed:
            if self.pending_CR is not None:self.close_line(self.pending_CR+1,'CR');self.pending_CR=None
            if self.body:self.close_line(self.total,'NO_FINAL_TERMINATOR')
            self.closed=True
        return {'decoded_bytes':self.total,'byte_patterns':dict(self.counts),'bare_CR_not_immediately_followed_by_LF':self.counts['CR']-self.counts['CRLF'],
            'bare_LF_not_immediately_preceded_by_CR':self.counts['LF']-self.counts['CRLF'],
            'CRCRLF_contains_one_CRLF_suffix_and_counts_are_not_disjoint':True,'first4_pattern_offsets':self.examples,
            'quote_agnostic_physical_line_counts':dict(self.lines),'maximum_physical_line_body_bytes':self.maximum_body,
            'first4_literal_empty_physical_lines':self.line_examples,
            'physical_lines_include_header_and_newlines_inside_quoted_fields':True,'text_values_decoded_or_retained':False,
            'physical_lines_or_CSV_records_claimed_as_effective_molecules':False,'EOF_does_not_synthesize_a_blank_line':True}
