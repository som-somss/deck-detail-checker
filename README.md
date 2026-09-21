# DECK 상세도 자동 검토기 V1

DXF 상세도와 Excel 집계표를 선택하여 TYPE별 데이터를 자동 비교하는 Windows GUI 프로그램입니다.

## V1 검토 범위
- DXF 상세도 재료표의 TYPE 자동 인식
- 상세도 재료표 데크 폭(B), 길이(L) 추출
- Excel `제원입력` 시트의 TYPE / 폭 / 길이 / DECK 수량 추출
- 상세도 재료표 ↔ Excel 데크 제원 비교
- 오류만 보기
- 결과 CSV 저장

> V1에서는 CAD **실제 형상 치수** 판독은 아직 지원하지 않습니다.
> 다음 버전에서 상세도 실제 형상 ↔ 재료표 ↔ Excel 3중 비교,
> 전단연결재 및 T/B/DT 철근 검토를 추가할 예정입니다.

## 실행
```bash
pip install -r requirements.txt
python main.py
```

## GitHub에서 EXE 만들기
1. 이 프로젝트 전체를 GitHub 저장소에 업로드합니다.
2. `Actions` → `Build Windows EXE`를 실행합니다.
3. 완료 후 `Artifacts`의 `DeckDetailChecker-Windows`를 받습니다.
4. 압축을 풀고 `DeckDetailChecker.exe`를 실행합니다.

## 테스트 기준
청람교 상세도/집계표 구조를 기준으로 V1을 작성했습니다.
