import copy
import unittest
from scripts.research_pilot import hold_reason


class PilotHoldTests(unittest.TestCase):
    def setUp(self):
        self.limits = {'max_generation_requests': 48, 'model_cost_policy': {'mode': 'stop_after_limit'}}
        self.row = {'return_code': 0, 'timed_out': False, 'pipeline_status': 'complete_success',
                    'prediction': 'A delivered answer that can be right or wrong.',
                    'benchmark_score': 0, 'cost_summary': {
                        'max_generation_requests': 48, 'resolved_cost_policy': {'mode': 'stop_after_limit'},
                        'budget_status': {'limit_reached': False},
                        **{key: 0 for key in ['accounting_persistence_failure_count', 'pending_call_count',
                           'response_usage_invalid_count', 'response_usage_missing_count',
                           'response_usage_unpriced_count', 'no_response_attempt_count']}}}

    def test_wrong_answer_does_not_hold_remaining_tasks(self):
        self.assertIsNone(hold_reason(self.row, self.limits))

    def test_completed_pipeline_without_delivery_holds(self):
        self.row['prediction']=''
        self.assertEqual(hold_reason(self.row,self.limits),'missing_delivered_prediction')

    def test_corrupted_delivery_holds(self):
        self.row['prediction_extraction']={'status':'error'}
        self.assertEqual(hold_reason(self.row,self.limits),'prediction_extraction_error')

    def test_incomplete_or_missing_accounting_holds(self):
        for key in ['pending_call_count', 'response_usage_missing_count', 'response_usage_unpriced_count', 'no_response_attempt_count']:
            row = copy.deepcopy(self.row)
            row['cost_summary'][key] = 1
            self.assertIsNotNone(hold_reason(row, self.limits))
        row = dict(self.row, cost_summary=None)
        self.assertEqual(hold_reason(row, self.limits), 'missing_cost_summary')

    def test_old_validation_budget_is_rejected(self):
        self.row['cost_summary']['max_generation_requests'] = 24
        self.assertEqual(hold_reason(self.row, self.limits), 'request_limit_mismatch')

    def test_interface_failure_holds_but_budget_stop_is_recorded(self):
        self.row.update(return_code=1, pipeline_status='failed')
        self.assertIsNotNone(hold_reason(self.row, self.limits))
        self.row['cost_summary']['budget_status']['limit_reached'] = True
        self.assertIsNone(hold_reason(self.row, self.limits))

    def test_budget_stop_does_not_hide_lost_usage(self):
        self.row.update(return_code=1, pipeline_status='failed')
        self.row['cost_summary']['budget_status']['limit_reached'] = True
        self.row['cost_summary']['response_usage_missing_count'] = 1
        self.assertIsNotNone(hold_reason(self.row, self.limits))


if __name__ == '__main__':
    unittest.main()
