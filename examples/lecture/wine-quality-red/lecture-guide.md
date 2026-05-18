# 강의 가이드: Wine Quality (Red) 데이터셋 — 단순 OLS 회귀분석

**데이터셋:** wine-quality-red/data.csv (1,599행, 12열)  
**추천 분석:** 단순 선형 회귀(simple OLS regression), 회귀 가정점검  
**난이도:** 입문–중급

---

## 1. 연구질문 및 가설 예시

### 연구질문
> "알코올 함량(alcohol)이 높을수록 적포도주의 관능 품질 점수(quality)가
> 유의미하게 높아지는가?"

- **귀무가설 H₀:** β₁ = 0 (alcohol이 quality를 선형 예측하지 않는다)
- **대립가설 H₁:** β₁ ≠ 0 (alcohol이 quality를 유의하게 예측한다)

### 회귀 모형
```
quality = β₀ + β₁ × alcohol + ε
```

---

## 2. 워크스페이스 준비

`$omr-start`에 제공할 자연어 프롬프트 예시:

```
적포도주 데이터에서 알코올 도수(alcohol)가 품질 점수(quality)를
예측하는지 단순 선형 회귀로 분석해 주세요.
```

또는 더 구체적으로:

```
Wine Quality 데이터로 quality ~ alcohol 단순 OLS 회귀를 수행하고,
R², 회귀계수, p-값을 보고해 주세요.
```

---

## 3. 데이터 배치

분석 워크스페이스에서 아래 경로에 파일을 복사합니다:

```
<워크스페이스 루트>/
└── 20_analysis/
    └── data/
        └── data.csv   ← wine-quality-red/data.csv 복사
```

---

## 4. `$omr-analyze` 프롬프트 및 기대 산출물

**`$omr-analyze` 프롬프트:**
```
quality ~ alcohol 단순 OLS 회귀분석을 수행해 주세요.
```

**기대 results.json 구조:**
```json
{
  "test": "simple_ols_regression",
  "label": "quality ~ alcohol",
  "statistic": 181.38,
  "p_value": 1.66e-38,
  "r_squared": 0.2267,
  "coefficients": {
    "intercept": 1.875,
    "alcohol": 0.361
  },
  "n": 1599
}
```

주요 출력 필드: `statistic`(F 값 또는 t 값), `p_value`, `r_squared`, `label`

---

## 5. 회귀 가정점검

단순 OLS 회귀의 주요 가정과 점검 방법을 함께 설명합니다:

| 가정 | 점검 방법 |
|------|-----------|
| 선형성 | 산점도(alcohol vs quality) |
| 독립성 | Durbin-Watson 통계량 |
| 등분산성(homoscedasticity) | 잔차 플롯(fitted vs residuals) |
| 정규성 | 잔차 Q-Q 플롯, Shapiro-Wilk 검정 |

강의 포인트: quality는 실제로 순서형(ordinal) 변수이므로 OLS의 정규성 가정이
완전히 충족되지 않습니다. 이를 "현실적 근사"로 사용하는 이유와 한계를 토론합니다.

---

## 6. 해석 포인트

- **회귀계수 β₁ ≈ 0.361:** alcohol이 1% 증가할 때 quality 점수가 평균 0.361점 증가합니다.
- **R² ≈ 0.227:** alcohol 단독으로 quality 분산의 약 22.7%를 설명합니다.
  → 나머지 77%는 다른 이화학적 변수(volatile_acidity, sulphates 등)에 의한 것임을 시사.
- **F-통계량 = 181.38, p < .001:** 모형이 통계적으로 유의합니다.
- **실질적 해석:** 알코올 도수가 높을수록 품질이 높은 경향이 있으나, 단일 변수로는
  예측력이 제한적입니다. 다중 회귀로 확장하면 설명력이 크게 향상됩니다.

### 추가 토론 주제
- quality를 3분위 범주(저/중/고)로 변환하면 어떤 검정이 적합한가? (χ², Kruskal-Wallis)
- 1,599행이라는 큰 표본에서 왜 작은 효과도 유의하게 나오는가? (통계적 검정력)
