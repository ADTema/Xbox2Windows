"""Replay the first pass-26 gate for wave 0 of group (0,0), dimensions <=32.
Generated HLSL remains in a private temporary directory. Never loads the package DLL.
Usage: python verify.py <Xbox2Windows checkout> <producer.bin> <LLVM-C.dll>
"""
from pathlib import Path
import csv
import hashlib
import re
import subprocess
import sys
import tempfile

repo, binary, llvm = map(Path, sys.argv[1:])
if not __debug__:
    raise RuntimeError("Run this verifier without Python's -O option.")
sys.path.insert(0, str(repo.resolve() / "tools"))
from pixel_aot import disassemble

code = binary.read_bytes()
assert hashlib.sha256(code).hexdigest() == "407c213a5cb6c92c08509f7a8783550d775fe5518399eab3eecf4c736a78e4ed"
isa = disassemble(code, str(llvm.resolve()), cpu=b"gfx1030", offsets=True)
ops = dict(isa)
branch = 0x2410
mn, offset = ops[branch].split()
assert mn == "s_cbranch_scc0"
skip = branch + 4 + 4 * int(offset)
assert skip == 0x26d8
assert next(pc for pc, op in isa if branch < pc < skip and op.startswith("ds_write")) == 0x25b0

# Backward dataflow slice, ending with the SCC used by the branch. Retain two
# more registers for measurements of the signed footprint comparisons.
need = {"scc", "s97", "s98"}
selected = []
for pc, line in reversed(isa):
    if not 0x22ac <= pc < branch: continue
    op, operands = line.split(" ", 1)
    args = operands.split(", ")
    cmp = op.startswith("s_cmp_")
    dst = "scc" if cmp else args[0]
    src = args if cmp else args[1:]
    sets_scc = op.startswith(("s_and_", "s_add_", "s_sub_", "s_lshl_", "s_bcnt"))
    writes = {dst, "scc"} if sets_scc else {dst}
    if not writes & need: continue
    selected.append((pc,op,dst,src))
    need -= writes
    if op.startswith("v_fmac_"):
        need.add(dst)
    need.update("scc" if t=="src_scc" else t for t in src
                if re.fullmatch(r"[vs]\d+|src_scc|exec_lo", t))
assert need == {"v1","v2","s28","s29","s30","s31","exec_lo"}, need

def store_replay():
    # Wave 0 has a zero base (v0 = 192 * (group-thread-index >> 5)).
    # The six rows below label the post-colour-transform source registers.
    # The stores and their immediate offsets come from the pinned input.
    sources = [(11,12,13), (17,18,19), (21,22,23), (25,26,27), (46,47,48), (49,50,52)]
    lines = ["for(uint j=lane;j<576;j+=32) tile[j]=0;",
             "GroupMemoryBarrierWithGroupSync();", "if(scc){", "uint addr0=0,addr1=0,addr54=0,addr55=0;"]
    for row, registers in enumerate(sources):
        for component, register in enumerate(registers):
            lines.append(f"uint tag{register}=1+({row}*32+lane)*3+{component};")
    stores = 0
    for pc, instruction in isa:
        if not branch < pc < skip:
            continue
        op, _, rest = instruction.partition(" ")
        if op in ("ds_write_b32", "ds_write2_b32"):
            operands, _, modifiers = rest.partition(" offset")
            fields = operands.split(", ")
            offsets = dict((key, int(value)) for key, value in
                           re.findall(r"offset(\d*):(\d+)", "offset"+modifiers))
            for n, source in enumerate(fields[1:]):
                byte_offset = offsets.get("", 0) if op == "ds_write_b32" else 4*offsets.get(str(n), 0)
                base = fields[0].replace("v", "addr")
                lines.append(f"tile[({base}+{byte_offset})/4]=tag{source[1:]};")
                stores += 1
        else:
            args = rest.split(", ")
            if args[0] not in ("v0","v1","v54","v55"):
                continue
            operands = [t.replace("v","addr") for t in args[1:]]
            if op == "v_mbcnt_lo_u32_b32" and operands == ["-1","0"]:
                expr = "lane"
            elif op in ("v_add_nc_u32_e32","v_or_b32_e32","v_mul_u32_u24_e32"):
                symbol = {"v_add_nc_u32_e32":"+","v_or_b32_e32":"|","v_mul_u32_u24_e32":"*"}[op]
                expr = symbol.join(operands)
            else:
                raise ValueError((hex(pc), instruction))
            lines.append(f"{args[0].replace('v','addr')}={expr};")
    assert stores == 18
    lines += ["}", "GroupMemoryBarrierWithGroupSync();",
              "for(uint j=lane;j<576;j+=32) result[g.x*576+j]=tile[j];"]
    return lines

def generate(cases, inclusive_x=False, stores=False):
    lines = ["RWStructuredBuffer<uint> result:register(u0);",
             "groupshared uint counts[32], laneWords[32];",
             "[numthreads(32,1,1)] void main(uint lane:SV_GroupIndex,uint3 g:SV_GroupID){",
             "uint width=0,height=0,scaleX=0,scaleY=0; switch(g.x) {"]
    for i,(w,h,x,y) in enumerate(cases):
        lines.append(f"case {i}: width={w};height={h};scaleX={x};scaleY={y};break;")
    lines += ["}", "uint v1=(lane&1)|((lane>>1)&14),v2=(lane>>1)&1;",
              "uint live=(v1<width/2 && v2<height/2); counts[lane]=live;",
              "GroupMemoryBarrierWithGroupSync(); uint pop=0; for(uint i=0;i<32;i++) pop+=counts[i];",
              "uint s28=asuint(scaleX/256.f),s29=asuint(scaleY/256.f),s30=0,s31=0,scc=0;"]
    declared = set(need) | {"scc"}
    for pc,op,dst,src in reversed(selected):
        args = ["scc" if t=="src_scc" else t for t in src]
        a=args[0]; b=args[1] if len(args)>1 else "0"
        if op.startswith(("v_readfirstlane","v_readlane")):
            # Lane zero is always live in this group for the tested dimensions.
            index="0" if op.startswith("v_readfirst") else b
            lines += [f"laneWords[lane]={a};","GroupMemoryBarrierWithGroupSync();"]
            expr=f"laneWords[{index}]"
        elif op.startswith("s_bcnt"): expr="pop"
        elif op.startswith("s_cmp_eq"): expr=f"({a}=={b})"
        elif op.startswith("s_cmp_lg"): expr=f"({a}!={b})"
        elif op.startswith("s_cmp_lt"):
            comparison = "<=" if inclusive_x and b == "33" else "<"
            expr=f"(asint({a}){comparison}asint({b}))"
        elif op.startswith("s_mov"): expr=a
        elif op.startswith("s_and"): expr=f"{a}&{b}"
        elif op.startswith("s_add"): expr=f"{a}+{b}"
        elif op.startswith("s_sub"): expr=f"{a}-{b}"
        elif op.startswith("v_or"): expr=f"{a}|{b}"
        elif op.startswith("v_lshlrev"): expr=f"{b}<<{a}"
        elif op.startswith("v_cvt_f32_u32"): expr=f"asuint(float({a}))"
        elif op.startswith("v_cvt_i32_f32"): expr=f"asuint(int(asfloat({a})))"
        elif op.startswith("v_rndne"): expr=f"asuint(round(asfloat({a})))"
        elif op.startswith("v_add_f32"): expr=f"asuint(asfloat({a})+asfloat({b}))"
        elif op.startswith(("v_fma_","v_fmac_")):
            f=lambda t: f"asfloat({t})" if re.fullmatch(r"[vs]\d+",t) else t
            c=dst if op.startswith("v_fmac") else args[2]
            expr=f"asuint(mad({f(a)},{f(b)},{f(c)}))"
        else: raise ValueError((hex(pc),op))
        lines.append(("" if dst in declared else "uint ")+dst+"="+expr+";")
        declared.add(dst)
        if op.startswith("s_and"): lines.append(f"scc=({dst}!=0);")
        if op.startswith("v_read"): lines.append("GroupMemoryBarrierWithGroupSync();")
    if stores:
        lines.insert(1, "groupshared uint tile[576];")
        lines += store_replay()
    else:
        lines.append("if(lane==0){uint k=g.x*4;result[k]=pop;result[k+1]=s98;result[k+2]=s97;result[k+3]=scc;}")
    lines.append("}")
    return "\n".join(lines)

def oracle(w,h,x,y):
    # Wave zero covers a 16x2 cell rectangle. When data exist in all 32
    # cells, the output endpoints are (0,0) and (31,3) before rescaling.
    count=min(16,w//2)*min(2,h//2)
    def extent(last,scale):
        return 3+round((last+0.5)*scale/256-0.5)-round(0.5*scale/256-0.5)
    ex,ey=extent(31,x),extent(3,y)
    return count,ex,ey,int(count==32 and ex<33 and ey<7)

cases=[(w,h,x,y) for w in (8,30,31,32) for h in (2,3,4)
       for x in (224,240,243,244,256) for y in (256,384)]
with tempfile.TemporaryDirectory() as tmp:
    shader=Path(tmp)/"gate.hlsl";shader.write_text(generate(cases))
    rows=[]
    for backend in ("hardware","warp"):
        out=subprocess.check_output([Path("gate.exe").resolve(),shader,
                                     backend,str(len(cases))],text=True)
        lines=out.splitlines();print(lines[0])
        assert len(lines[1:])==len(cases)
        for case,line in zip(cases,lines[1:]):
            actual=tuple(map(int,line.split()))
            expected=oracle(*case)
            # Inactive lane data on the real device is unspecified. Do not use
            # subgroup footprint observations as evidence on partial waves.
            assert actual[0]==expected[0] and actual[3]==expected[3], (case,actual,expected)
            if actual[0]==32: assert actual==expected,(case,actual,expected)
            rows.append((backend,*case,actual[0],actual[1] if actual[0]==32 else "",
                         actual[2] if actual[0]==32 else "",actual[3]))
    shader.write_text(generate(cases, inclusive_x=True))
    for backend in ("hardware", "warp"):
        run = subprocess.check_output([Path("gate.exe").resolve(), shader,
                                       backend, str(len(cases))], text=True)
        observations = run.splitlines()[1:]
        assert len(observations) == len(cases)
        changed = [case for case, line in zip(cases, observations)
                   if int(line.split()[3]) != oracle(*case)[3]]
        assert changed == [(32, 4, 244, 256)], (backend, changed)
        print(f"{backend}: inclusive-X control changed only {changed[0]}")
    store_cases = [(32,4,243,256), (32,4,244,256), (31,4,243,256)]
    shader.write_text(generate(store_cases, stores=True))
    store_rows = []
    for backend in ("hardware", "warp"):
        run = subprocess.check_output([Path("gate.exe").resolve(), shader,
                                      backend, str(len(store_cases)), "576"], text=True)
        observations = run.splitlines()[1:]
        assert len(observations) == len(store_cases)
        for case, line in zip(store_cases, observations):
            words = list(map(int,line.split()))
            expected = list(range(1,577)) if oracle(*case)[3] else [0]*576
            assert words == expected, (backend, case, "LDS word mismatch")
            store_rows.append((backend,*case,len(words),sum(word!=0 for word in words)))
    with Path("lds-results.csv").open("w",newline="") as f:
        writer=csv.writer(f)
        writer.writerow("backend width height scale_x_256 scale_y_256 words_checked tagged_words".split())
        writer.writerows(store_rows)
    print("LDS tagged-store replay: all 576 words matched for each of 3 cases on both backends")
    with Path("gate-results.csv").open("w",newline="") as f:
        writer=csv.writer(f);writer.writerow("backend width height scale_x_256 scale_y_256 lanes extent_x extent_y fallthrough".split());writer.writerows(rows)
    print(f"{len(rows)} comparisons passed; {len(selected)} decoded instructions in predicate slice; skip target {skip:#x}")
