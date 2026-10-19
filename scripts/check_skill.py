"""Standalone offline skill metadata and resource validation."""
import re
import yaml
from common import ROOT

def main():
    source=(ROOT/'SKILL.md').read_text(encoding='utf-8')
    match=re.match(r'^---\n(.*?)\n---\n',source,re.S)
    assert match,'Missing YAML frontmatter'
    data=yaml.safe_load(match.group(1))
    assert data['name']=='role-showcase-remix'
    assert isinstance(data.get('description'),str) and data['description'].strip()
    for relative in re.findall(r'\]\(([^)]+)\)',source):
        if not relative.startswith('http'): assert (ROOT/relative).is_file(),relative
    ui=yaml.safe_load((ROOT/'agents/openai.yaml').read_text(encoding='utf-8'))
    assert 25<=len(ui['interface']['short_description'])<=64
    assert '$role-showcase-remix' in ui['interface']['default_prompt']
    print('PASS standalone skill metadata and referenced resources')

if __name__=='__main__':main()
