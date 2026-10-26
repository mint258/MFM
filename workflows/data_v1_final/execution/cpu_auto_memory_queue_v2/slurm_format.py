"""Strict Slurm fields, including colon/slash keys present on this site.

Keep the frozen v1 record slicing and ambiguity checks.  The field alphabet
additionally recognizes ':' so AllocNode:Sid and ReqB:S:C:T cannot become part
of the preceding value.  '/' (for CPUs/Task) remains a valid key character.
No values, resource declarations or admission thresholds are normalized.
"""
import re


def need(ok, code):
    if not ok:
        raise ValueError(code)


def fields(raw):
    need(isinstance(raw, str), "SCONTROL_TEXT_REQUIRED")
    matches = list(re.finditer(r"(?<!\S)([A-Za-z][A-Za-z0-9_./+:-]*)=", raw))
    need(matches, "SCONTROL_FIELDS_UNAVAILABLE")
    need(not raw[:matches[0].start()].strip(), "SCONTROL_FIELD_PREFIX_UNRECOGNIZED")
    result = {"_raw": raw}
    for index, match in enumerate(matches):
        key = match[1]
        need(key not in result, "DUPLICATE_OR_AMBIGUOUS_SCONTROL_FIELD:" + key)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        result[key] = raw[match.end():end].strip()
    return result


def parse_scontrol_jobs(text):
    """Parse all-user oneliner/multiline records; repeated IDs fail closed."""
    need(isinstance(text, str), "SCONTROL_TEXT_REQUIRED")
    if not text.strip() or text.strip() == "No jobs in the system":
        return []
    starts = list(re.finditer(r"(?<!\S)JobId=", text))
    need(starts and not text[:starts[0].start()].strip(), "SCONTROL_JOB_RECORDS_REQUIRED")
    jobs = [fields(text[match.start():starts[index + 1].start()
                         if index + 1 < len(starts) else len(text)])
            for index, match in enumerate(starts)]
    need(all(re.fullmatch(r"\d+(?:_\d+|\+\d+)?", job.get("JobId", "")) for job in jobs),
         "SCONTROL_JOB_ID_INVALID")
    need(len({job["JobId"] for job in jobs}) == len(jobs), "DUPLICATE_JOB_RECORD")
    return jobs
