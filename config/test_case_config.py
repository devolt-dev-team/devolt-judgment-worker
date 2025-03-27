import os

from common.enums import CodeLanguage
from common.fileutils import load_json_file


class TestCaseConfig:
    _TEST_CASES = load_json_file(os.path.join(os.path.dirname(__file__), "json", "test_cases_inputs_and_expected.json"))

    _TEST_CASES_LIMITS = load_json_file(os.path.join(os.path.dirname(__file__), "json", "exec_time_and_memory_limits.json"))
    _TEST_CASES_TIME_LIMITS = _TEST_CASES_LIMITS.get("timeLimits")
    _TEST_CASES_MEM_LIMITS = _TEST_CASES_LIMITS.get("memoryLimits")

    _TEST_CASE_LIMITS_BONUS = load_json_file(os.path.join(os.path.dirname(__file__), "json", "exec_time_and_memory_language_bonus.json"))
    _TEST_CASE_LIMITS_TIME_BONUS = _TEST_CASE_LIMITS_BONUS.get("timeBonus")
    _TEST_CASE_LIMITS_MEMORY_BONUS = _TEST_CASE_LIMITS_BONUS.get("memoryBonus")

    @staticmethod
    def get_test_cases(challenge_id: int) -> list:
        return TestCaseConfig._TEST_CASES[str(challenge_id)]

    @staticmethod
    def get_memory_limit(challenge_id: int, code_language: CodeLanguage) -> int:
        return TestCaseConfig._TEST_CASES_MEM_LIMITS[str(challenge_id)] + TestCaseConfig._TEST_CASE_LIMITS_MEMORY_BONUS[code_language.value]

    @staticmethod
    def get_time_limit(challenge_id: int, code_language: CodeLanguage) -> float:
        return TestCaseConfig._TEST_CASES_TIME_LIMITS[str(challenge_id)] + TestCaseConfig._TEST_CASE_LIMITS_TIME_BONUS[code_language.value]

