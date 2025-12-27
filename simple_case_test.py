import asyncio
import sys
sys.path.insert(0, '.')
from server.services.rag_service import rag_service

async def simple_test():
    print('Testing case context retrieval...')
    cases = await rag_service._find_relevant_case_context('domestic violence Virginia', max_cases=2)
    print(f'Found {len(cases)} cases')
    for case in cases:
        print(f'  {case.get("case_type", "Unknown")}: {case.get("outcome", "Unknown")}')

asyncio.run(simple_test())
















