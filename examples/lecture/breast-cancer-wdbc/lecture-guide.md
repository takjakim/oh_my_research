# 강의 가이드: Breast Cancer WDBC 데이터셋 — 2집단 t-검정 + χ² 검정

**데이터셋:** breast-cancer-wdbc/data.csv (569행, 32열)  
**추천 분석:** 독립표본 t-검정(radius_mean ~ diagnosis), χ² 검정(범주화 변수 × diagnosis)  
**난이도:** 중급  
**MVP 범위 안내:** 로지스틱 회귀는 oh_my_research MVP 범위 밖입니다.

---

## 1. 연구질문 및 가설 예시

### 연구질문 A (2집단 t-검정)
> "악성(M) 종양과 양성(B) 종양은 세포핵 평균 반지름(radius_mean)에서
> 유의미하게 다른가?"

- **귀무가설 H₀:** μ_M = μ_B (악성과 양성의 radius_mean 평균이 동일하다)
- **대립가설 H₁:** μ_M ≠ μ_B (양측 검정, 유의수준 α = 0.05)

### 연구질문 B (χ² 검정)
> "radius_mean을 중앙값 기준으로 이분화(high/low)했을 때,
> 진단 결과(M/B)와 관련성이 있는가?"

- **귀무가설 H₀:** diagnosis와 radius_group은 독립이다
- **대립가설 H₁:** diagnosis와 radius_group 사이에 연관이 있다

---

## 2. 워크스페이스 준비

`$omr-start`에 제공할 자연어 프롬프트 예시:

```
유방암 진단 데이터에서 악성(M)과 양성(B) 집단의
세포핵 반지름 평균(radius_mean)에 차이가 있는지
독립표본 t-검정으로 분석해 주세요.
```

χ² 검정 시나리오:

```
radius_mean을 중앙값 기준으로 상위(high)/하위(low)로 나눠서
악성·양성 진단과의 관련성을 카이제곱 검정으로 분석해 주세요.
```

---

## 3. 데이터 배치

분석 워크스페이스에서 아래 경로에 파일을 복사합니다:

```
<워크스페이스 루트>/
└── 20_analysis/
    └── data/
        └── data.csv   ← breast-cancer-wdbc/data.csv 복사
```

---

## 4A. `$omr-analyze` 프롬프트 및 기대 산출물 — 2집단 t-검정

**`$omr-analyze` 프롬프트:**
```
radius_mean을 diagnosis(M/B) 집단 간 독립표본 t-검정으로 비교해 주세요.
```

**기대 results.json 구조:**
```json
{
  "test": "independent_t_test",
  "label": "radius_mean ~ diagnosis (M vs B)",
  "statistic": 22.64,
  "p_value": 5.20e-76,
  "group_means": {
    "M": 17.46,
    "B": 12.15
  },
  "cohens_d": 2.14,
  "n_M": 212,
  "n_B": 357
}
```

주요 출력 필드: `statistic`(t 값), `p_value`, `group_means`, `cohens_d`, `label`

---

## 4B. `$omr-analyze` 프롬프트 및 기대 산출물 — χ² 검정

**`$omr-analyze` 프롬프트:**
```
radius_mean을 중앙값(약 13.37)을 기준으로 high/low로 범주화한 후,
diagnosis와의 독립성을 카이제곱 검정으로 분석해 주세요.
```

**기대 results.json 구조:**
```json
{
  "test": "chi_square_independence",
  "label": "diagnosis × radius_group (high/low by median)",
  "statistic": 244.5,
  "p_value": 3.2e-55,
  "df": 1,
  "contingency_table": {
    "M_high": 196,
    "M_low": 16,
    "B_high": 90,
    "B_low": 267
  },
  "cramers_v": 0.656
}
```

주요 출력 필드: `statistic`(χ² 값), `p_value`, `df`, `cramers_v`, `label`

---

## 5. 로지스틱 회귀에 대한 안내

로지스틱 회귀(logistic regression)는 이진 결과(M/B)를 여러 연속형 변수로 예측하는 데
적합한 분석이지만, **oh_my_research MVP 범위 밖**입니다.

현재 MVP에서 지원하는 분석:
- 독립표본 t-검정 (2집단 평균 비교)
- 일원 ANOVA (3집단 이상 평균 비교)
- 단순 OLS 회귀 (연속형 예측변수 → 연속형 결과)
- χ² 독립성 검정 (범주형 × 범주형)

로지스틱 회귀가 필요한 경우 Python(sklearn, statsmodels) 또는 R을 사용하세요.

---

## 6. 해석 포인트

### t-검정 결과
- t = 22.64, p < .001 → 귀무가설 기각.
- 악성 종양의 radius_mean(평균 17.46 μm)이 양성(12.15 μm)보다 유의미하게 큽니다.
- Cohen's d = 2.14 → 매우 큰 효과 크기. 집단 간 차이가 임상적으로도 의미 있습니다.

### χ² 검정 결과
- χ²(1) = 244.5, p < .001 → 진단과 radius_group은 유의하게 연관됩니다.
- Cramer's V = 0.656 → 강한 연관성. radius_mean의 이분화만으로도 M/B를 잘 구별합니다.

### 강의 포인트
- 569행 중 M:B = 212:357 (불균형). 집단 불균형이 t-검정 해석에 미치는 영향을 토론합니다.
- 30개 특징 변수 중 어느 변수가 집단 차이가 가장 큰지 탐색적으로 비교하는 실습 가능.
- "통계적 유의성"과 "임상적 유의성"의 차이를 논의하기에 좋은 데이터셋입니다.
- diagnosis = B(양성)이 다수 집단임을 강조하여 "기저율(base rate)" 개념을 소개합니다.
