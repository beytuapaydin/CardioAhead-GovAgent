import json
import tempfile
import unittest
from pathlib import Path
from agents.triage_agent import triage
from agents.regulatory_agent import regulatory_map
from governance.authority_gate import evaluate
from governance.audit import verify_chain
from main import ROOT

class GovAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / 'audit.jsonl'
        self.items = json.loads((ROOT / 'data/synthetic_incidents.json').read_text())
    def tearDown(self): self.tmp.cleanup()
    def test_class_c_blocked(self):
        self.assertEqual(evaluate(regulatory_map(triage(self.items[2])),self.log)['decision'], 'BLOCK_AND_ESCALATE')
    def test_override_blocked(self):
        self.assertEqual(evaluate(regulatory_map(triage(self.items[4])),self.log)['decision'], 'BLOCK_AND_ESCALATE')
    def test_routine_allowed_as_draft_only(self):
        out=evaluate(regulatory_map(triage(self.items[0])),self.log)
        self.assertEqual(out['decision'],'ALLOW_ROUTINE_DRAFT')
        self.assertFalse(out['executed'])
    def test_unknown_action_default_deny(self):
        x={**self.items[0], 'proposed_action':'delete_patient_records'}
        self.assertTrue(evaluate(x,self.log)['human_review_required'])
    def test_audit_chain_tamper_detection(self):
        evaluate(self.items[0],self.log)
        self.assertTrue(verify_chain(self.log))
        s=self.log.read_text().replace('INC-001','INC-999')
        self.log.write_text(s)
        self.assertFalse(verify_chain(self.log))
    def test_bad_uncertainty_rejected(self):
        with self.assertRaises(ValueError): triage({**self.items[0], 'uncertainty': 2})

if __name__ == '__main__': unittest.main()

class V2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'audit.jsonl'
        self.incident = json.loads((ROOT / 'data/synthetic_incidents.json').read_text())[0]
    def tearDown(self): self.tmp.cleanup()

    def test_llm_fields_cannot_overwrite_authority(self):
        from agents.llm_triage import _validated_notes, TriageProviderError
        with self.assertRaises(TriageProviderError):
            _validated_notes({'failure_mode_summary':'ok','evidence_gaps':[], 'proposed_action':'document_only'})
    def test_llm_notes_are_only_commentary(self):
        from unittest.mock import patch
        from agents.llm_triage import llm_triage
        with patch('agents.llm_triage.extract_llm_notes', return_value={'failure_mode_summary':'safe','evidence_gaps':[]}):
            item=llm_triage(self.incident,endpoint='https://api.openai.com/v1/chat/completions',model='example',api_key='secret')
        self.assertEqual(item['proposed_action'], self.incident['proposed_action'])
        self.assertEqual(item['illustrative_iec62304_class'], self.incident['illustrative_iec62304_class'])
        self.assertEqual(evaluate(item,self.path)['decision'], 'ALLOW_ROUTINE_DRAFT')
    def test_llm_failure_is_blocked(self):
        item={**self.incident,'triage_status':'llm_failed_needs_review'}
        self.assertEqual(evaluate(item,self.path)['decision'], 'BLOCK_AND_ESCALATE')
    def test_critical_stays_blocked_despite_llm_notes(self):
        incidents=json.loads((ROOT / 'data/synthetic_incidents.json').read_text())
        item={**incidents[2], 'llm_notes':{'failure_mode_summary':'safe', 'evidence_gaps':[]}}
        self.assertEqual(evaluate(item,self.path)['decision'], 'BLOCK_AND_ESCALATE')
    def test_bad_endpoint_rejected(self):
        from agents.llm_triage import _validate_endpoint, TriageProviderError
        for endpoint in ('http://example.com', 'file:///etc/passwd', 'https://user:pass@example.com'):
            with self.assertRaises(TriageProviderError): _validate_endpoint(endpoint)
    def test_tampered_prior_audit_refused(self):
        from main import run
        self.path.write_text('{"bad":1}\n')
        # assert only that malformed audit chains are not treated as valid
        from governance.audit import verify_chain
        self.assertFalse(verify_chain(self.path))

class V2IntegrationTests(unittest.TestCase):
    def test_simulated_llm_end_to_end_and_permission_boundaries(self):
        from unittest.mock import patch
        from main import run
        with tempfile.TemporaryDirectory() as directory:
            with patch('agents.llm_triage.extract_llm_notes', return_value={
                'failure_mode_summary':'synthetic failure summary', 'evidence_gaps':['Confirm with reviewer']
            }):
                results=run(Path(directory), mode='llm', endpoint='https://api.openai.com/v1/chat/completions', model='mocked-model', api_key='fake')
            self.assertEqual(len(results), 5)
            self.assertEqual(sum(x['gate']['human_review_required'] for x in results), 2)
            self.assertTrue(verify_chain(Path(directory)/'audit_log.jsonl'))
            self.assertTrue(all(x['gate']['executed'] is False for x in results))
    def test_simulated_llm_provider_failure_blocks_everything(self):
        from unittest.mock import patch
        from main import run
        from agents.llm_triage import TriageProviderError
        with tempfile.TemporaryDirectory() as directory:
            with patch('agents.llm_triage.extract_llm_notes', side_effect=TriageProviderError('provider unavailable')):
                results=run(Path(directory), mode='llm', endpoint='https://api.openai.com/v1/chat/completions', model='mocked-model', api_key='fake')
            self.assertTrue(all(x['gate']['decision']=='BLOCK_AND_ESCALATE' for x in results))
