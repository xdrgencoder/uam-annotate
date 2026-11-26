# -*- coding: utf-8 -*-
"""UAM CT6 及物性标注构建工具
.idx 格式来自 CT6 后端 Codings.py:
  header 6*uint32(intsNeeded,featLen,codLen,fieldLen,roleLen,commentLen)
  featBytes  ';'.join(features)
  codDat     每条 24 字节: u16 sid, u16 pid, u32 start, u32 end, u8 flags, 3 pad, u64 bitmap
"""
import struct, os, re

FEATURES = [
    "clause",
    "material", "mental", "relational", "verbal", "behavioural", "existential",
    "perception", "emotion", "cognition",
    "attributive", "identifying",
    "Actor", "Goal", "Range", "Beneficiary",
    "Senser", "Phenomenon",
    "Carrier", "Attribute", "Identified", "Identifier",
    "Sayer", "Verbiage", "Receiver", "Target",
    "Behaver", "Existent",
    "location_time", "location_place", "manner", "cause",
    "accompaniment", "matter", "role", "extent",
]
FSET = set(FEATURES)

LABEL = {
    "location_time": "Location: Time", "location_place": "Location: Place",
    "manner": "Manner", "cause": "Cause", "accompaniment": "Accompaniment",
    "matter": "Matter", "role": "Role", "extent": "Extent",
}

ROLE_FEATS = {"Actor", "Goal", "Range", "Beneficiary", "Senser", "Phenomenon",
              "Carrier", "Attribute", "Identified", "Identifier", "Sayer",
              "Verbiage", "Receiver", "Target", "Behaver", "Existent"}
CIRC_FEATS = {"location_time", "location_place", "manner", "cause",
              "accompaniment", "matter", "role", "extent"}
PROC_FEATS = {"material", "mental", "relational", "verbal", "behavioural", "existential"}


# ---------------------------------------------------------------- 二进制读写
def feats_to_bits(feats):
    b = 0
    for f in feats:
        b |= 1 << FEATURES.index(f)
    return b


def bits_to_feats(bits):
    out, i = [], 0
    while bits:
        if bits & 1:
            out.append(FEATURES[i])
        bits >>= 1
        i += 1
    return out


def write_idx(path, recs):
    fb = ";".join(FEATURES).encode("utf-8")
    cod = b""
    for r in recs:
        flags = 4
        if r.get("comment"):
            flags |= 1
        rec = struct.pack("2H2IB", r["sid"], r["pid"], r["start"], r["end"], flags)
        rec += b"\x00" * (16 - len(rec))
        rec += struct.pack("Q", feats_to_bits(r["feats"]))
        assert len(rec) == 24
        cod += rec
    cdat = "\n".join("%d\t%s" % (r["sid"], r["comment"].replace("\n", "%NL"))
                     for r in recs if r.get("comment")).encode("utf-8")
    rdat = "\n".join("%d\t%s" % (r["sid"], r["role"])
                     for r in recs if r.get("role")).encode("utf-8")
    with open(path, "wb") as f:
        f.write(struct.pack("6I", 1, len(fb), len(cod), 0, len(rdat), len(cdat)))
        f.write(fb); f.write(cod)
        if rdat:
            f.write(rdat)
        if cdat:
            f.write(cdat)


def read_idx(path):
    d = open(path, "rb").read()
    in_n, fl, cl, fdl, rl, cml = struct.unpack("6I", d[:24])
    off = 24
    feats = d[off:off + fl].decode("utf-8").split(";")
    off += fl
    cod = d[off:off + cl]
    off += cl
    rolemap = {}
    if rl:
        for line in d[off:off + rl].decode("utf-8").splitlines():
            if "\t" in line:
                k, v = line.split("\t", 1)
                rolemap[int(k)] = v
    rl_ = 16 + 8 * in_n
    out = []
    for i in range(cl // rl_):
        ch = cod[i * rl_:(i + 1) * rl_]
        sid, pid, st, en, flags = struct.unpack("2H2IB", ch[:13])
        bitmap, = struct.unpack("Q", ch[16:24])
        out.append(dict(sid=sid, pid=pid, start=st, end=en,
                        feats=bits_to_feats(bitmap), role=rolemap.get(sid, "")))
    return out, feats


# ---------------------------------------------------------------- 空白归一检索
class Sent:
    """在原句上做忽略换行/多空格的子串定位"""

    def __init__(self, text, start, end):
        self.text = text
        self.s = start
        self.e = end
        raw = text[start:end]
        self.norm = []
        self.n2o = []          # norm 下标 -> 原句绝对偏移
        self.n2e = []          # norm 下标 -> 该字符在原句中的结束偏移
        i = 0
        while i < len(raw):
            if raw[i].isspace():
                j = i
                while j < len(raw) and raw[j].isspace():
                    j += 1
                self.norm.append(" ")
                self.n2o.append(start + i)
                self.n2e.append(start + j)
                i = j
            else:
                self.norm.append(raw[i])
                self.n2o.append(start + i)
                self.n2e.append(start + i + 1)
                i += 1
        self.norm = "".join(self.norm)

    def find(self, quote, lo=None, hi=None, label="", nth=None):
        q = re.sub(r"\s+", " ", quote).strip()
        lo = self.s if lo is None else lo
        hi = self.e if hi is None else hi
        # 原句偏移 -> norm 下标
        a = 0
        while a < len(self.n2o) and self.n2o[a] < lo:
            a += 1
        b = len(self.n2o)
        while b > a and self.n2e[b - 1] > hi:
            b -= 1
        seg = self.norm[a:b]
        idxs = []
        p = seg.find(q)
        while p >= 0:
            # 词边界过滤: 避免 "he" 命中 "her"/"the"
            left_ok = (p == 0) or (not (seg[p - 1].isalnum() or seg[p - 1] == "'")) \
                      or (not (q[0].isalnum() or q[0] == "'"))
            e = p + len(q)
            right_ok = (e == len(seg)) or (not (seg[e].isalnum() or seg[e] == "'")) \
                       or (not (q[-1].isalnum() or q[-1] == "'"))
            if left_ok and right_ok:
                idxs.append(p)
            p = seg.find(q, p + 1)
        if not idxs:
            raise ValueError("%s 未找到 %r\n  区间: %r" % (label, q, self.text[lo:hi]))
        if nth is not None:
            if len(idxs) <= nth:
                raise ValueError("%s 只找到 %d 处 %r, 需要第 %d 处"
                                 % (label, len(idxs), q, nth + 1))
            p = idxs[nth]
        else:
            if len(idxs) > 1:
                raise ValueError("%s 出现 %d 次 %r" % (label, len(idxs), q))
            p = idxs[0]
        # 若引用串以空格结尾/开头会有偏差, 这里取非空白边界
        st = self.n2o[a + p]
        en = self.n2e[a + p + len(q) - 1]
        return st, en


# ---------------------------------------------------------------- 构建
ERRORS = []


def build(ann, bounds, text, mirror_offset=None, collect=False):
    """ann: {句号: [ (从句原文, 过程类型串, [(角色,片段), ...], [子从句...]) ]}
    返回 (records, table)。mirror_offset 不为空时, 额外生成平移后的第二份。
    """
    recs, table = [], []
    sid = 0
    for sno in sorted(ann):
        st, en = bounds[sno]
        S = Sent(text, st, en)
        cursor = st

        def emit(quote, pt, parts, subs, pid, lo, hi):
            nonlocal sid
            try:
                a, b = S.find(quote, lo, hi, "S%d" % sno)
            except Exception as ex:
                if not collect:
                    raise
                ERRORS.append(str(ex))
                return hi
            sid += 1
            this = sid
            feats = ["clause"] + pt.split()
            for f in feats:
                if f not in FSET:
                    raise ValueError("未知特征 %r (S%d)" % (f, sno))
            _spec = [f for f in feats if f != "clause"]
            _role = ""
            if _spec and not any(f in PROC_FEATS for f in _spec):
                _role = LABEL.get(_spec[-1], _spec[-1])
            recs.append(dict(sid=this, pid=pid, start=a, end=b, feats=feats, role=_role))
            table.append(dict(sid=this, sent=sno, pid=pid, start=a, end=b,
                              span=text[a:b], feats="+".join(feats),
                              kind="clause" if any(f in PROC_FEATS for f in feats) else "any"))
            for part in parts:
                role, q = part[0], part[1]
                _ = None
                nth = part[2] if len(part) > 2 else None
                if role not in FSET:
                    raise ValueError("未知角色 %r (S%d)" % (role, sno))
                try:
                    pa, pb = S.find(q, a, b, "S%d/%s" % (sno, role), nth)
                except Exception as ex:
                    if not collect:
                        raise
                    ERRORS.append(str(ex))
                    continue
                sid += 1
                recs.append(dict(sid=sid, pid=this, start=pa, end=pb,
                                 feats=["clause", role],
                                 role=LABEL.get(role, role)))
                table.append(dict(sid=sid, sent=sno, pid=this, start=pa, end=pb,
                                  span=text[pa:pb], feats="clause+" + role, kind="part"))
            for sub in subs:
                emit(sub[0], sub[1], sub[2], sub[3] if len(sub) > 3 else [],
                      this, a, b)
            return b

        for cl in ann[sno]:
            cursor = emit(cl[0], cl[1], cl[2], cl[3] if len(cl) > 3 else [], 0, cursor, en)

    # 结构修正 1: 前置环境段(无谓体)并入后随小句
    def _sn(pos):
        for i, (bs, be) in enumerate(bounds):
            if bs <= pos < be:
                return i
        return -1

    for x in recs:
        if any(f in PROC_FEATS for f in x["feats"]):
            continue
        if x["pid"] != 0:
            continue
        if text[x["end"]:x["end"] + 1] != ",":
            continue
        cand = [q for q in recs
                if q["pid"] == 0 and q["start"] > x["end"]
                and q["start"] - x["end"] <= 2
                and any(f in PROC_FEATS for f in q["feats"])
                and _sn(q["start"]) == _sn(x["start"])]
        if cand:
            q = min(cand, key=lambda y: y["start"])
            q["start"] = x["start"]
            x["pid"] = q["sid"]

    # 结构修正 2: 关系小句挂到紧邻其前的名词性段(并在跨度上并入该段)
    REL = ("that", "which", "who", "whose", "where", "when", "whereby")
    for c in recs:
        if not any(f in PROC_FEATS for f in c["feats"]):
            continue
        head = re.sub(r"\s+", " ", text[c["start"]:c["start"] + 9]).strip().lower()
        if not any(head.startswith(m) for m in REL):
            continue
        cand = [x for x in recs
                if x["sid"] != c["sid"] and x["pid"] == c["pid"]
                and not any(f in PROC_FEATS for f in x["feats"])
                and x["end"] <= c["start"] and c["start"] - x["end"] <= 2
                and _sn(x["start"]) == _sn(c["start"])]
        # 强调句 "it is X that Y" 的 that-小句不是关系小句, 不并入
        cand = [y for y in cand if not ({"Identified", "Identifier"} & set(y["feats"]))]
        if cand:
            x = max(cand, key=lambda y: y["end"])
            x["end"] = c["end"]
            c["pid"] = x["sid"]

    # 结构修正 3: 若某子段被同级兄弟段(如 Phenomenon / Identifier)完整包含,
    # 则改为该兄弟段的子段, 形成 从句 > 参与者 > 关系小句 的正确树形
    for _ in range(4):
        changed = False
        for r in recs:
            if r["pid"] == 0:
                continue
            if not any(f in PROC_FEATS for f in r["feats"]):
                continue          # 只允许"小句"挂到参与者段下面, 反之不行(避免环)
            cand = [x for x in recs
                    if x["pid"] == r["pid"] and x["sid"] != r["sid"]
                    and x["start"] <= r["start"] and x["end"] >= r["end"]
                    and not any(f in PROC_FEATS for f in x["feats"])]
            if cand:
                best = min(cand, key=lambda x: x["end"] - x["start"])
                if best["sid"] != r["pid"]:
                    r["pid"] = best["sid"]
                    changed = True
        if not changed:
            break

    if mirror_offset:
        base = len(recs)
        mir = []
        for r in recs:
            sid += 1
            mir.append(dict(sid=sid, pid=(r["pid"] + base if r["pid"] else 0),
                            start=r["start"] + mirror_offset,
                            end=r["end"] + mirror_offset, feats=list(r["feats"]),
                            role=r.get("role", "")))
            table.append(dict(sid=sid, sent=None, pid=r["pid"] + base if r["pid"] else 0,
                              start=r["start"] + mirror_offset, end=r["end"] + mirror_offset,
                              span=text[r["start"] + mirror_offset:r["end"] + mirror_offset],
                              feats="+".join(r["feats"]),
                              kind="mirror"))
        recs += mir
    recs.sort(key=lambda r: r["sid"])
    return recs, table
