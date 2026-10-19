"""Questionnaire state and automatic FilmCraft production after agent review."""
import argparse,json,math
from pathlib import Path
from fractions import Fraction
from common import load_json,save_json,sha256,state_dir,project_path,approve
import asset_ops,planner_ops,filmcraft_ops,render_ops

QUESTIONS={
 'mode':'这批做完整角色展示重排，还是剧情剪辑？',
 'group_size':'每条使用3个还是4个完整角色片段？',
 'target_count':'本批要多少条？也可选择按配额尽可能多做。',
 'max_uses':'每个片段本批最多使用几次？',
 'quota_scope':'配额仅算本批，还是跨批累计？',
 'output_width':'输出宽度是多少？',
 'output_height':'输出高度是多少？',
 'output_fps':'输出帧率是多少？',
 'preserve_original_audio':'是否保留片段原声、不另加音乐？',
 'naming':'使用自动编号命名，还是指定业务命名格式？',
 'authorization_text':'是否按上述规则自动完成切分、排列、FilmCraft工程、导出和交付？保留用户实际授权原文。'
}

def normalize(answers):
    missing=[{'field':k,'question':v} for k,v in QUESTIONS.items() if k not in answers or answers[k] is None or answers[k]=='']
    if missing:return None,missing
    a=dict(answers)
    if a['mode']!='showcase':raise ValueError('Automatic native production currently supports showcase; story requires its independent project script and validation')
    if type(a['group_size']) is not int or a['group_size'] not in (3,4):raise ValueError('Choose 3 or 4 roles per video')
    if type(a['max_uses']) is not int or a['max_uses']<1:raise ValueError('Invalid segment use limit')
    if a['quota_scope']!='batch':raise ValueError('Cross-batch quotas require consolidated remaining-budget audit; automatic uniform quota batch cannot silently reset history')
    if a['target_count']=='capacity':pass
    elif type(a['target_count']) is not int or a['target_count']<1:raise ValueError('Invalid requested video count')
    for key in ('output_width','output_height'):
        if type(a[key]) is not int or a[key]<2 or a[key]%2:raise ValueError('Output dimensions must be positive even integers')
    fps=Fraction(str(a['output_fps']))
    if fps<=0:raise ValueError('Invalid FPS')
    a['output_fps']=str(fps)
    if a['preserve_original_audio'] is not True:raise ValueError('Automatic native adapter currently preserves original audio only')
    for key in ('distinct_sources','unique_sets','unique_pairs','balance_positions','exact_uses'):
        if key in a and type(a[key]) is not bool:raise ValueError('Constraint must be boolean: '+key)
    if a['naming'] not in ('generic','custom'):raise ValueError('Choose generic or custom naming')
    if a['naming']=='custom':
        extra=[{'field':k,'question':v} for k,v in [('id_prefix','本批统一ID是什么？'),('material_name','素材名是什么？'),('category','分类标签是什么？'),('tag','混剪来源标签是什么？'),('fixed_suffix','固定后缀是什么？'),('size_label','与实际尺寸对应的命名标签是什么？')] if not a.get(k)]
        if extra:return None,extra
    if not isinstance(a['authorization_text'],str) or not a['authorization_text'].strip():raise ValueError('Actual user authorization required')
    return a,[]

def intake(args):
    answers=load_json(project_path(args.project,args.answers));a,missing=normalize(answers)
    output={'status':'questions_pending' if missing else 'ready','engine':'FilmCraft','answers':a if a else answers,'questions':missing}
    save_json(state_dir(args.project)/'intake.json',output)
    print(json.dumps(output,ensure_ascii=False,indent=2))

def produce(args):
    root=Path(args.project).resolve();intakepath=state_dir(root)/'intake.json';intake=load_json(intakepath)
    if intake['status']!='ready':raise ValueError('Questionnaire incomplete; ask missing questions before production')
    previous_delivery=state_dir(root)/'automatic-delivery.json'
    if previous_delivery.exists() and load_json(previous_delivery)['intake_sha256']!=sha256(intakepath):raise ValueError('Completed batch answers changed; create a new batch instead of silently reusing quota')
    a,missing=normalize(intake['answers'])
    if missing:raise ValueError('Questionnaire incomplete')
    checkpoint=load_json(state_dir(root)/'automation.json');spec=state_dir(root)/'segments.json'
    if checkpoint.get('intake_sha256')!=sha256(intakepath) or checkpoint.get('segments_sha256')!=sha256(spec):raise ValueError('Questionnaire or reviewed boundaries changed')
    if checkpoint.get('visual_review_complete') is not True or checkpoint.get('unresolved')!=[]:raise ValueError('Finish actual full-frame review and resolve ambiguous boundaries first')
    cfgpath=state_dir(root)/'batch.json';cfg=load_json(cfgpath)
    desired={'segments_per_video':a['group_size'],'target_count':None if a['target_count']=='capacity' else a['target_count'],'max_uses':a['max_uses'],'exact_uses':a.get('exact_uses',False),
             'output_width':a['output_width'],'output_height':a['output_height'],'output_fps':a['output_fps'],
             'preserve_original_audio':True,'engine':'FilmCraft'}
    for key,default in [('distinct_sources',False),('unique_sets',True),('unique_pairs',False),('balance_positions',False)]:desired[key]=a.get(key,default)
    planpath=state_dir(root)/'plan.json'
    if planpath.exists():
        plan=load_json(planpath)
        # Capacity is resolved to a number by planner; it is allowed to resume.
        for k,v in desired.items():
            if k=='target_count' and v is None:continue
            if plan['config'].get(k)!=v:raise ValueError('Existing plan differs from answers; use a new batch instead of overwriting')
    else:
        cfg.update(desired);save_json(cfgpath,cfg)
    # The agent records real advance authorization. No generated text substitutes for it.
    approve(root,'cut','.remix/segments.json',a['authorization_text'])
    asset_ops.cut(argparse.Namespace(project=str(root),segments='.remix/segments.json',only=None))
    if not planpath.exists():
        if a['target_count']=='capacity':
            n=len(load_json(state_dir(root)/'segments-cut.json')['segments']);k=a['group_size']
            bound=n*a['max_uses']//k
            if cfg.get('unique_sets',True):bound=min(bound,math.comb(n,k) if n>=k else 0)
            else:bound=min(bound,math.perm(n,k) if n>=k else 0)
            if cfg.get('distinct_sources'):
                from collections import Counter
                groups=Counter(x['asset_id'] for x in load_json(state_dir(root)/'segments-cut.json')['segments'])
                dp=[1]+[0]*k
                for size in groups.values():
                    for j in range(k,0,-1):dp[j]+=dp[j-1]*size
                bound=min(bound,dp[k] if cfg.get('unique_sets',True) else dp[k]*math.factorial(k))
            if cfg.get('unique_pairs') and k>=2:bound=min(bound,math.comb(n,2)//math.comb(k,2))
            if bound<1:raise ValueError('Insufficient complete roles for requested group size')
            cfg['target_count']=bound;save_json(cfgpath,cfg)
        planner_ops.plan(argparse.Namespace(project=str(root),config='.remix/batch.json',budget_seconds=60))
    planner_ops.audit(argparse.Namespace(project=str(root)))
    approve(root,'render','.remix/plan.json',a['authorization_text'])
    runargs=argparse.Namespace(project=str(root),only=None,cli=args.cli)
    filmcraft_ops.build(runargs);filmcraft_ops.export(runargs);filmcraft_ops.deliver(runargs)
    state=render_ops.rendered_state(root)
    if a['naming']=='custom':
        prefix=a['id_prefix']+'-'+a['material_name']+'迭'
        if not all(Path(v['path']).name.startswith(prefix) for v in state['videos']):
            planner_ops.naming(argparse.Namespace(project=str(root),id_prefix=a['id_prefix'],material_name=a['material_name'],category=a['category'],tag=a['tag'],fixed_suffix=a['fixed_suffix'],size_label=a['size_label'],author_map=a.get('author_map')))
            approve(root,'rename','.remix/naming.json',a['authorization_text'])
            planner_ops.rename(argparse.Namespace(project=str(root),mapping='.remix/naming.json'))
    render_ops.verify(argparse.Namespace(project=str(root),only=None))
    save_json(state_dir(root)/'automatic-delivery.json',{'status':'technical_delivery_complete','engine':'FilmCraft','intake_sha256':sha256(intakepath),
              'videos':render_ops.rendered_state(root)['videos'],'usage':load_json(state_dir(root)/'usage.json'),
              'content_review':'agent must inspect actual output first/last and all joins before final handoff','subjective_audio':'requires actual listening; technical validation is not listening'})
    import audio_review_ops
    audio_review_ops.prepare(argparse.Namespace(project=str(root),only=None,extract=False))
    print('Automatic native technical delivery complete; finish actual output content review before handoff')

def register(sub):
    p=sub.add_parser('auto-intake');p.add_argument('--project',required=True);p.add_argument('--answers',default='.remix/intake-answers.json');p.set_defaults(func=intake)
    p=sub.add_parser('auto-produce');p.add_argument('--project',required=True);p.add_argument('--cli');p.set_defaults(func=produce)
