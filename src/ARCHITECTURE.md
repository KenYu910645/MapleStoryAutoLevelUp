# MapleStoryAutoLevelUp src 구조와 구동 흐름

이 문서는 `src` 디렉터리의 역할과, 프로그램이 실제로 어떻게 동작하는지를 빠르게 파악하기 위한 개요입니다.

## 1. src 디렉터리 구성

```text
src/
  main.py                    # UI 모드 진입점
  engine/
    MapleStoryAutoLevelUp.py # 핵심 엔진(봇 로직, 루프, 상태머신, 감지/명령 조합)
    FiniteStateMachine.py    # 상태 전이 관리
    HealthMonitor.py         # HP/MP/EXP 모니터링, 포션 자동 사용
    RuneSolver.py            # 룬 감지/해결 로직
    Profiler.py              # 프레임 처리 성능 측정
  input/
    KeyBoardController.py    # 키 입력 시뮬레이션 스레드
    KeyBoardListener.py      # 단축키(F1/F2/F12 등) 리스너
    GameWindowCapturor.py    # 게임 화면 캡처(Windows)
    GameWindowCapturorForMac.py # 게임 화면 캡처(macOS)
  states/
    base_state.py            # 상태 인터페이스
    hunting.py               # 일반 사냥 상태
    finding_rune.py          # 룬 탐색 상태
    near_rune.py             # 룬 근접 상태
    solving_rune.py          # 룬 미니게임 해결 상태
    patrol.py                # 순찰 모드 상태
    auxiliary.py             # 보조 모드 상태
  ui/
    ui.py                    # PySide6 메인 윈도우
    AutoBotController.py     # UI와 엔진 사이 브리지
  utils/
    common.py, logger.py ... # 공통 함수(템플릿 매칭, 좌표 계산, 로깅 등)
```

## 2. 실행 진입점(Entry Points)

### A. UI 모드(권장)
- 실행: `python -m src.main`
- 흐름:
  1. `QApplication` 생성
  2. `AutoBotController` 생성
  3. `MainWindow` 생성
  4. UI 시그널과 엔진 시그널 연결
  5. 사용자가 Start 누르면 컨트롤러가 엔진 시작

### B. CLI 모드(디버그/개발)
- 실행: `python -m src.engine.MapleStoryAutoLevelUp`
- 흐름:
  1. argparse로 옵션 파싱(`--cfg`, `--disable_viz`, `--record` 등)
  2. 기본/플랫폼/사용자 설정 YAML 병합
  3. `MapleStoryAutoBot` 생성 후 `start()` 호출
  4. OpenCV 디버그 창 루프 실행

## 3. 핵심 객체와 책임

### `MapleStoryAutoBot` (엔진의 중심)
- 설정/리소스 로딩
  - 맵 이미지(`minimaps/.../map.png`)
  - 경로 이미지(`route*.png`)
  - 몬스터 템플릿(`monster/...`)
  - 네임태그/룬/UI 템플릿
- 런타임 좌표 유지
  - 미니맵 위치, 캐릭터 위치(게임 화면/글로벌 맵), 감시 타이머
- 모듈 조합
  - `KeyBoardController`, `GameWindowCapturor`, `HealthMonitor`, `RuneSolver`, `FiniteStateMachine`

### `FiniteStateMachine`
- 상태 등록/전이 규칙 등록
- 매 프레임 `state.on_frame()` 실행
- `state.check_transitions()` 결과가 있으면 안전 전이 수행

### `KeyBoardController` (독립 스레드)
- 명령 문자열(`left_right up_down action`)을 받아 실제 키 입력 수행
- 버프 스킬 주기적 사용
- 게임 창 활성 상태 체크
- FPS 제한으로 입력 과부하 방지

### `HealthMonitor` (독립 스레드)
- 프레임에서 HP/MP/EXP 바를 추정
- 임계치/쿨다운 기반 포션 키 입력
- 포션 소진 감시 옵션 시 귀환 키 입력

### `RuneSolver`
- 룬 경고/활성 메시지 감지
- 룬 위치 탐색
- 미니게임 화살표 인식 후 방향키 순차 입력

## 4. 상태(State) 기반 동작

기본 상태와 전이(정상 모드 기준):

1. `hunting`
2. `finding_rune`
3. `near_rune`
4. `solving_rune`

전이 개요:
- `hunting -> finding_rune`: 룬 활성/경고 메시지 감지
- `finding_rune -> near_rune`: 룬 위치가 잡힘
- `finding_rune -> solving_rune`: 룬 미니게임 진입 감지
- `near_rune -> solving_rune`: 룬 미니게임 진입 감지
- `near_rune -> finding_rune`: 근접 상태 타임아웃
- `solving_rune -> hunting`: 미니게임 종료

추가 모드:
- `aux`: 보조 상태(동작 최소화)
- `patrol`: 좌우 순찰 + 공격

## 5. 프레임 단위 메인 루프

`MapleStoryAutoBot.loop()`는 내부적으로 `run_once()`를 반복 호출합니다.

프레임 처리의 큰 흐름:

1. 최신 게임 프레임 확보(캡처 모듈)
2. 미니맵/플레이어 위치 추정
3. 경로 기반 이동 명령 계산 (`update_cmd_by_route`)
4. 몬스터 인식 기반 공격 명령 보정 (`update_cmd_by_mob_detection`)
5. 상태 머신 실행 (`fsm.do_state_stuff`)
6. 디버그 이미지/경로맵 시각화 갱신(옵션)
7. UI 모드라면 시그널로 디버그 프레임 전달
8. FPS 제한 sleep

중요 포인트:
- 엔진이 "무엇을 할지" 명령을 결정하고,
- 키보드 컨트롤러 스레드가 "어떻게 누를지"를 실행합니다.

## 6. 스레드 구조 요약

기본적으로 다음 흐름이 병렬로 돌아갑니다.

1. 엔진 메인 스레드: 프레임 처리 + 상태 판단
2. 키보드 스레드: 지속 입력/버프/액션 실행
3. 체력 모니터 스레드(옵션): HP/MP 감시 및 포션
4. 화면 캡처 스레드(캡처 백엔드 내부): 최신 프레임 공급

종료 시 `terminate_threads()`가 각 모듈의 종료 플래그를 내려 정리합니다.

## 7. 설정 파일이 동작에 미치는 영향

설정은 `config/*.yaml`에서 로드되며, 실제 동작에 강하게 반영됩니다.

- 공격 방식: `aoe_skill` / `directional`
- 키 매핑: 점프/텔레포트/공격/포션/귀환
- FPS 제한: 메인 루프, 키보드, 체력 모니터, 캡처
- 룬 감지 좌표/임계치
- 몬스터 탐색 범위, 경로 색상 코드 행동 매핑

즉, 코드 구조는 공통이고 "맵/캐릭터/환경별 차이"는 대부분 YAML 튜닝으로 흡수하는 방식입니다.

## 8. 처음 코드 읽을 때 추천 순서

1. `src/main.py` (UI 진입)
2. `src/ui/AutoBotController.py` (UI-엔진 연결)
3. `src/engine/MapleStoryAutoLevelUp.py` (`start`, `run_once`, `loop`)
4. `src/engine/FiniteStateMachine.py` + `src/states/*`
5. `src/input/KeyBoardController.py` / `src/engine/HealthMonitor.py`
6. `src/engine/RuneSolver.py`
65
이 순서로 보면 "전체 실행 흐름 -> 세부 알고리즘" 순으로 이해가 쉽습니다.
