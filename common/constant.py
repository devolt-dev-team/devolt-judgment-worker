import os

from common.enums import CodeLanguage
from common.util import load_json_file


TEST_CASES = load_json_file(os.path.join(os.path.dirname(__file__), "test_cases_inputs_and_expected.json"))

TEST_CASES_LIMITS = load_json_file(os.path.join(os.path.dirname(__file__), "exec_time_and_memory_limits.json"))
TEST_CASES_TIME_LIMITS = TEST_CASES_LIMITS.get("timeLimits")
TEST_CASES_MEM_LIMITS = TEST_CASES_LIMITS.get("memoryLimits")

TEST_CASE_LIMITS_BONUS = load_json_file(os.path.join(os.path.dirname(__file__), "exec_time_and_memory_language_bonus.json"))
TEST_CASE_LIMITS_TIME_BONUS = TEST_CASE_LIMITS_BONUS.get("timeBonus")
TEST_CASE_LIMITS_MEMORY_BONUS = TEST_CASE_LIMITS_BONUS.get("memoryBonus")

CODE_FILE_NAME = {
    CodeLanguage.JAVA17.value: 'Main.java',
    CodeLanguage.NODEJS20.value: 'main.js',      # CommonJS
    CodeLanguage.NODEJS20ESM.value: 'main.mjs',  # ESM
    CodeLanguage.PYTHON3.value: 'main.py',
    CodeLanguage.C11.value: 'main.c',
    CodeLanguage.CPP17.value: 'main.cpp'
}

if __name__ == "__main__":
    print(TEST_CASES)
    print(TEST_CASES_TIME_LIMITS)
    print(TEST_CASES_MEM_LIMITS)
    print(TEST_CASE_LIMITS_TIME_BONUS)
    print(TEST_CASE_LIMITS_MEMORY_BONUS)
