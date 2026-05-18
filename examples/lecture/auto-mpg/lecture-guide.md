# 강의 가이드: Auto MPG 데이터셋 — OLS 회귀 + 결측 데이터 처리 시연

**데이터셋:** auto-mpg/data.csv (398행, 9열)  
**추천 분석:** 단순 OLS 회귀(mpg ~ weight), 결측값 처리(horsepower의 6개 결측)  
**난이도:** 입문–중급 (결측 처리 패턴 시연 포함)

---

## 1. 연구질문 및 가설 예시

### 연구질문
> "차량 중량(weight)이 클수록 연비(mpg)가 유의미하게 낮아지는가?"

- **귀무가설 H₀:** β₁ = 0 (weight가 mpg를 선형 예측하지 않는다)
- **대립가설 H₁:** β₁ < 0 (weight가 증가할수록 mpg가 감소한다, 단측 검정 가능)

### 회귀 모형
```
mpg = β₀ + β₁ × weight + ε
```

### 결측 처리 예비질문
> "horsepower를 독립변수로 추가할 경우, 6개 결측 행을 어떻게 처리해야 하는가?"

---

## 2. 워크스페이스 준비

`$omr-start`에 제공할 자연어 프롬프트 예시:

```
자동차 데이터에서 차량 무게(weight)가 연비(mpg)에 영향을 주는지
단순 선형 회귀로 분석해 주세요.
```

또는 결측 시연을 포함하는 버전:

```
Auto MPG 데이터로 mpg ~ horsepower 회귀분석을 시도해 주세요.
horsepower에 결측값이 있는데 어떻게 처리해야 할지도 알려주세요.
```

---

## 3. 데이터 배치

분석 워크스페이스에서 아래 경로에 파일을 복사합니다:

```
<워크스페이스 루트>/
└── 20_analysis/
    └── data/
        └── data.csv   ← auto-mpg/data.csv 복사
```

---

## 4A. `$omr-analyze` 프롬프트 및 기대 산출물 — mpg ~ weight (결측 없음)

**`$omr-analyze` 프롬프트:**
```
mpg ~ weight 단순 OLS 회귀분석을 수행해 주세요.
```

**기대 results.json 구조:**
```json
{
  "test": "simple_ols_regression",
  "label": "mpg ~ weight",
  "statistic": 1145.79,
  "p_value": 1.08e-101,
  "r_squared": 0.6918,
  "coefficients": {
    "intercept": 46.317,
    "weight": -0.00768
  },
  "n": 398
}
```

주요 출력 필드: `statistic`(F 값), `p_value`, `r_squared`, `label`

---

## 4B. `$omr-analyze` 프롬프트 — mpg ~ horsepower (결측 처리 blocked-pending 시연)

**`$omr-analyze` 프롬프트:**
```
mpg ~ horsepower 단순 OLS 회귀분석을 수행해 주세요.
```

**기대 동작 — blocked-pending 상태:**

`omr-analyze`는 horsepower에 결측값(6개 빈 셀)이 존재함을 감지하고
분석을 일시 중단합니다. 예상 응답 메시지:

```
[omr-analyze] STATUS: blocked-pending
REASON: horsepower 컬럼에 6개의 결측값이 발견되었습니다.
분석을 계속하려면 결측 처리 전략을 선택해 주세요:
  (A) 결측 행 삭제 (listwise deletion) → 392행으로 축소
  (B) 평균값으로 대체 (mean imputation)
  (C) 분석 중단
```

이 blocked-pending 패턴은 oh_my_research의 안전한 분석 흐름을 보여줍니다.
사용자가 (A)를 선택하면 분석이 재개됩니다.

**결측 처리 후 기대 results.json:**
```json
{
  "test": "simple_ols_regression",
  "label": "mpg ~ horsepower",
  "statistic": 847.05,
  "p_value": 7.03e-83,
  "r_squared": 0.6059,
  "coefficients": {
    "intercept": 39.936,
    "horsepower": -0.1578
  },
  "n": 392,
  "missing_rows_removed": 6
}
```

---

## 5. 해석 포인트

### mpg ~ weight 결과
- **회귀계수 β₁ ≈ −0.00768:** 차량 중량이 1lb 증가할 때 연비가 약 0.008 mpg 감소합니다.
  중량 1,000lb 증가 → 연비 약 7.68 mpg 감소.
- **R² ≈ 0.692:** weight 단독으로 mpg 분산의 69.2%를 설명합니다. 매우 강한 단일 예측변수.
- **음의 관계:** 중량-연비 음의 상관은 물리적으로 직관적이며, 인과 주장 시 주의가 필요합니다.

### 결측 데이터 시연 포인트
- horsepower 결측 6개(~1.5%)는 소규모이지만 회귀 모형 구축 전 반드시 처리해야 합니다.
- **listwise deletion:** 단순하지만 결측이 MCAR(완전 무작위 결측)이 아니면 편향 우려.
- **mean imputation:** 분포를 보존하나 분산을 과소추정하는 문제가 있습니다.
- 강의에서 "왜 omr-analyze가 결측에서 멈추는가?"를 논의하는 것이 학습 효과가 높습니다.

### 추가 토론 주제
- cylinders와 origin을 범주형으로 더미 코딩하여 다중 회귀로 확장
- model_year를 통제변수로 추가하면 연도별 연비 향상 트렌드 파악 가능
