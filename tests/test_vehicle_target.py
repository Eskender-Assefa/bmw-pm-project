from types import SimpleNamespace
from backend.schemas import Cohort
from backend.vehicle_target import PartInference, resolve_target, CACHE
import openai

def item(feature='General comfort',title='My lower back aches on long drives',description='Give me more support behind my back.'):
    return SimpleNamespace(feature=feature,title=title,description=description,category='C05',revision=1,evidence_samples=[])

def test_local_mapping_keeps_category_separate(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    target=resolve_target(item('Touch screen, operation'),Cohort())
    assert target.method=='local' and target.components==['screen'] and target.concept=='screen'
    assert resolve_target(item('Seat belts'),Cohort()).components==[]
    assert resolve_target(item('Price','Reduce the purchase price','Make it less expensive'),Cohort()).components==[]

def test_ai_interprets_wording_and_caches_by_revision(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-only-placeholder');CACHE.clear();calls=[]
    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(output_parsed=PartInference(components=['seats'],concept='seats',confidence='high',reason='Lower-back support refers to the seat.',supporting_quote='My lower back aches'))
    monkeypatch.setattr(openai,'OpenAI',lambda **kwargs:SimpleNamespace(responses=SimpleNamespace(parse=parse)))
    req=item();result=resolve_target(req,Cohort(),allow_live=True)
    assert result.method=='ai' and result.components==['seats'] and req.category=='C05'
    resolve_target(req,Cohort(),allow_live=True);assert len(calls)==1
    req.revision=2;resolve_target(req,Cohort(),allow_live=True);assert len(calls)==2
    assert calls[0]['store'] is False

def test_bad_quote_or_provider_failure_falls_back(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-only-placeholder');CACHE.clear()
    result=PartInference(components=['brakes'],concept=None,confidence='high',reason='bad',supporting_quote='not present in the request')
    monkeypatch.setattr(openai,'OpenAI',lambda **kwargs:SimpleNamespace(responses=SimpleNamespace(parse=lambda **kwargs:SimpleNamespace(output_parsed=result))))
    assert resolve_target(item('Touch screen, operation'),Cohort(),allow_live=True).method=='local'

def test_ambiguous_ai_cannot_highlight_an_unjustified_part(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-only-placeholder');CACHE.clear()
    result=PartInference(components=['seats'],concept='seats',confidence='low',reason='Ambiguous',supporting_quote='My lower back aches')
    monkeypatch.setattr(openai,'OpenAI',lambda **kwargs:SimpleNamespace(responses=SimpleNamespace(parse=lambda **kwargs:SimpleNamespace(output_parsed=result))))
    mapped=resolve_target(item(),Cohort(),allow_live=True)
    assert mapped.components==[] and mapped.concept is None


def test_live_provider_is_not_contacted_without_opt_in(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-only-placeholder')
    def forbidden(**kwargs):raise AssertionError('Provider should not be constructed')
    monkeypatch.setattr(openai,'OpenAI',forbidden)
    assert resolve_target(item('Touch screen, operation'),Cohort()).method=='local'


def test_invalid_credential_is_actionable_without_exposing_error_text(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-only-placeholder');CACHE.clear()
    class CredentialError(Exception):status_code=401
    def fail(**kwargs):raise CredentialError('private provider error text')
    monkeypatch.setattr(openai,'OpenAI',lambda **kwargs:SimpleNamespace(responses=SimpleNamespace(parse=fail)))
    result=resolve_target(item('Touch screen, operation'),Cohort(),allow_live=True)
    assert result.method=='local' and result.components==['screen']
    assert 'API key' in result.notice and 'private provider' not in result.notice
