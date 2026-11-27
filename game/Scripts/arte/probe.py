import unreal
out=[]
for n in sorted(dir(unreal)):
    if 'GeometryScript' in n and not n.startswith('GeometryScript_') : continue
    if n.startswith('GeometryScript_') or n.startswith('GeometryScriptLibrary'):
        c=getattr(unreal,n)
        ms=[m for m in dir(c) if not m.startswith('_')]
        keep=[m for m in ms if any(k in m for k in ('append','static_mesh','normal','material','asset','copy','combine'))]
        out.append(f"{n}: {keep}")
open(unreal.Paths.project_saved_dir()+'probe.txt','w').write('\n'.join(out))
unreal.log('[PROBE] ok')
