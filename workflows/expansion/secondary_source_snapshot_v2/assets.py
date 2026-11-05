"""CPU-only SOURCE_CODE_ASSET whole SHA, stable frames and exact safe extraction."""
import hashlib,json,os,stat,zipfile
from pathlib import Path
from . import contracts as C
Q=C.Q


def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode)


def stable_claim(before,after,count,digest,ref):
    Q.need(before==after and count==ref['bytes'] and digest==ref['sha256'],'SOURCE_ASSET_SHA_BYTES_OR_FRAME_CHANGED')


def member_inventory(z,rows,embedded=None):
    names={}
    for info in z.infolist():
        name=C.safe_relative(info.filename);mode=info.external_attr>>16
        Q.need(name not in names and not info.is_dir() and stat.S_IFMT(mode) in (0,stat.S_IFREG)
          and not info.flag_bits&1,'NO_DUPLICATE_DIRECTORY_SYMLINK_SPECIAL_OR_ENCRYPTED_MEMBER')
        names[name]=info
    wanted=set(rows)|({embedded} if embedded is not None else set())
    Q.need(set(names)==wanted,'NO_EXTRA_OR_MISSING_SOURCE_ASSET_MEMBERS')
    for name,r in rows.items():Q.need(names[name].file_size==r['bytes'],'EXACT_MEMBER_UNCOMPRESSED_BYTE_DECLARATION')
    if embedded is not None:Q.need(0<names[embedded].file_size<=2<<20,'SMALL_EMBEDDED_SOURCE_MANIFEST_ONLY')
    return names


def directories(root,parent):
    root=Path(root);target=root
    for piece in Path(parent).relative_to(root).parts:
        target=target/piece
        try:target.mkdir(mode=0o700)
        except FileExistsError:pass
        s=target.lstat();Q.need(stat.S_ISDIR(s.st_mode) and not target.is_symlink() and s.st_uid==1264,'FRESH_OWNED_REGULAR_SOURCE_PARENT')
    Q.need(root.resolve()==root and root in (parent,*parent.parents),'EXTRACTION_STAYS_IN_FRESH_ROOT')


def extract(ref,manifest,rows,target,budget,git=False):
    p=Q.literal(ref['path']);Q.need(not any(x.is_symlink() for x in (p,*p.parents)),'SOURCE_CODE_ASSET_NO_SYMLINK')
    before=frame(p.lstat());Q.need(stat.S_ISREG(before[-1]) and before[5]==1264 and before[2]==ref['bytes'],'OWN_ACTUAL_SOURCE_CODE_ASSET')
    target=Q.literal(target);Q.need(not target.exists() and C.ROOT/'artifacts' in target.parents,'FRESH_SOURCE_EXTRACTION_ONLY')
    embedded='asset_manifest.json' if git else manifest.get('archive_manifest_member')
    if embedded is not None:C.safe_relative(embedded);Q.need(embedded not in rows,'MANIFEST_MEMBER_NOT_A_GIT_LISTED_SOURCE_ALIAS')
    with p.open('rb') as stream:
        Q.need(frame(os.fstat(stream.fileno()))==before,'ACTUAL_OPENED_SOURCE_ASSET_FD')
        h=hashlib.sha256();count=0
        while True:
            budget.check();block=stream.read(1<<20)
            if not block:break
            count+=len(block);Q.need(count<=ref['bytes'],'BOUNDED_SOURCE_ARCHIVE');h.update(block)
        stable_claim(before,frame(os.fstat(stream.fileno())),count,h.hexdigest(),ref)
        stream.seek(0)
        with zipfile.ZipFile(stream) as z:
            names=member_inventory(z,rows,embedded)
            if embedded is not None:
                raw=z.read(embedded);Q.need(json.loads(raw)==manifest,'EMBEDDED_MANIFEST_SAME_JSON_SEMANTICS')
            budget.check(sum(r['bytes'] for r in rows.values()));target.mkdir(mode=0o700)
            extracted=[]
            for name in sorted(rows):
                r=rows[name];dest=target/name;directories(target,dest.parent)
                fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);hh=hashlib.sha256();n=0
                with os.fdopen(fd,'wb') as out,z.open(names[name]) as src:
                    while True:
                        budget.check();block=src.read(min(1<<20,r['bytes']-n+1))
                        if not block:break
                        n+=len(block);Q.need(n<=r['bytes'],'NO_SOURCE_ZIP_BOMB_BEYOND_DECLARED_BYTES');hh.update(block);out.write(block)
                    out.flush();os.fsync(out.fileno())
                Q.need(n==r['bytes'] and hh.hexdigest()==r['sha256'],'EACH_SOURCE_MEMBER_EXACT_ORIGINAL_SHA')
                executable=name in ('bin/native-git','lib/ld-linux-x86-64.so.2') if git else r['git_mode']=='100755'
                dest.chmod(0o555 if executable else 0o444)
                extracted.append({'relative_path':name,'bytes':n,'sha256':hh.hexdigest(),'actual_frame':list(frame(dest.lstat()))})
        Q.need(frame(os.fstat(stream.fileno()))==before==frame(p.lstat()),'WHOLE_EXTRACTION_SOURCE_ASSET_STABLE_FD_AND_PATH')
    return {'archive_reference':ref,'current_archive_frame':list(before),'whole_archive_SHA_before_extract':True,
      'fresh_root':str(target),'files':extracted,'embedded_manifest_member':embedded,'source_kind':'SOFTWARE_ASSET' if git else 'SOURCE_CODE_ASSET'}


def verify_tree(root,rows,budget,expected_frames=None,allow_git=False):
    root=Path(root);seen={};frames={}
    allowed_dirs={q.as_posix() for name in rows for q in Path(name).parents if q.as_posix()!='.'}
    for p in root.rglob('*'):
        relative=p.relative_to(root).as_posix()
        if allow_git and (relative=='.git' or relative.startswith('.git/')):
            Q.need(not p.is_symlink(),'.GIT_ONLY_NEW_OWNED_METADATA_NOT_SYMLINK');continue
        s=p.lstat();Q.need(not p.is_symlink() and (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)),'REGULAR_SNAPSHOT_ONLY')
        if p.is_dir():
            Q.need(relative in allowed_dirs,'NO_EXTRA_EMPTY_SOURCE_DIRECTORY');continue
        Q.need(relative in rows and s.st_uid==1264,'NO_EXTRA_SNAPSHOT_FILE_OR_OWNER_CHANGE')
        budget.check();r=rows[relative];before=frame(s);h=hashlib.sha256();n=0
        with p.open('rb') as f:
            Q.need(frame(os.fstat(f.fileno()))==before,'SNAPSHOT_FD_MATCH')
            while True:
                budget.check();block=f.read(1<<20)
                if not block:break
                n+=len(block);Q.need(n<=r['bytes'],'BOUNDED_SNAPSHOT_SOURCE');h.update(block)
            stable_claim(before,frame(os.fstat(f.fileno())),n,h.hexdigest(),r)
        Q.need(frame(p.lstat())==before,'SNAPSHOT_PATH_FRAME_STABLE')
        if expected_frames is not None:Q.need(list(before)==expected_frames[relative],'SOURCE_FRAME_CHANGED_BY_CHECKS')
        seen[relative]=h.hexdigest();frames[relative]=list(before)
    Q.need(set(seen)==set(rows),'NO_SOURCE_MISSING_AFTER_EXTRACTION_OR_CHECKS')
    return {'all_files_SHA_equal':True,'count':len(seen),'frames':frames,'git_metadata_excluded_only':allow_git}
