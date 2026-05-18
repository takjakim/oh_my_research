# 강의 가이드: Iris 데이터셋 — 일원 ANOVA + 2집단 t-검정

**데이터셋:** iris/data.csv (150행, 5열)  
**추천 분석:** 일원 분산분석(one-way ANOVA), 독립표본 t-검정  
**난이도:** 입문

---

## 1. 연구질문 및 가설 예시

### 연구질문 A (ANOVA)
> "세 붓꽃 품종(setosa, versicolor, virginica) 사이에 꽃잎 길이(petal_length)의
> 평균에 유의미한 차이가 있는가?"

- **귀무가설 H₀:** μ_setosa = μ_versicolor = μ_virginica (세 집단의 petal_length 평균이 동일하다)
- **대립가설 H₁:** 적어도 하나의 집단 평균이 다르다 (p < 0.05)

### 연구질문 B (t-검정)
> "versicolor와 virginica의 꽃잎 길이(petal_length) 평균에 유의미한 차이가 있는가?"

- **귀무가설 H₀:** μ_versicolor = μ_virginica
- **대립가설 H₁:** μ_versicolor ≠ μ_virginica (양측 검정)

---

## 2. 워크스페이스 준비

`$omr-start`에 제공할 자연어 프롬프트 예시:

```
세 붓꽃 품종(setosa, versicolor, virginica)의 꽃잎 길이(petal_length)가
품종에 따라 유의미하게 다른지 일원 분산분석으로 검정하고 싶어요.
```

또는 더 구체적으로:

```
Iris 데이터로 petal_length가 species(3집단)에 따라 다른지
one-way ANOVA로 분석해 주세요. 유의수준 0.05로 설정해 주세요.
```

---

## 3. 데이터 배치

분석 워크스페이스에서 아래 경로에 파일을 복사합니다:

```
<워크스페이스 루트>/
└── 20_analysis/
    └── data/
        └── data.csv   ← iris/data.csv 복사
```

---

## 4. `$omr-analyze` 프롬프트 및 기대 산출물

### 분석 A: 일원 ANOVA

**`$omr-analyze` 프롬프트:**
```
petal_length ~ species로 일원 ANOVA를 수행해 주세요.
```

**기대 검정 및 results.json 구조:**
```json
{
  "test": "one_way_anova",
  "label": "petal_length ~ species",
  "statistic": 1180.16,
  "p_value": 2.86e-91,
  "df_between": 2,
  "df_within": 147,
  "group_means": {
    "Iris-setosa": 1.464,
    "Iris-versicolor": 4.260,
    "Iris-virginica": 5.552
  }
}
```

주요 출력 필드: `statistic`(F 값), `p_value`, `label`

### 분석 B: 2집단 t-검정 (versicolor vs virginica)

**`$omr-analyze` 프롬프트:**
```
versicolor와 virginica 두 품종만 필터링하여
petal_length의 집단 간 차이를 독립표본 t-검정으로 검정해 주세요.
```

**기대 results.json 구조:**
```json
{
  "test": "independent_t_test",
  "label": "petal_length: Iris-versicolor vs Iris-virginica",
  "statistic": -12.62,
  "p_value": 3.74e-22,
  "group_means": {
    "Iris-versicolor": 4.260,
    "Iris-virginica": 5.552
  },
  "cohens_d": 2.52
}
```

---

## 5. 해석 포인트

### ANOVA 결과
- F(2, 147) = 1180.16, p < .001 → 귀무가설 기각.
- 세 품종 간에 petal_length 평균 차이가 통계적으로 유의합니다.
- 사후검정(post-hoc, 예: Tukey HSD)을 통해 어느 쌍이 다른지 파악할 수 있습니다.
  (oh_my_research MVP에서는 ANOVA F-검정까지 제공합니다.)

### t-검정 결과
- t = −12.62, p < .001, Cohen's d = 2.52 (매우 큰 효과 크기).
- versicolor(평균 4.26 cm) vs virginica(평균 5.55 cm) 간 차이가 실질적으로 의미 있습니다.
- setosa는 petal_length가 매우 작아(평균 1.46 cm) 다른 두 품종과 극단적으로 분리되므로,
  setosa 포함 t-검정은 setosa vs. (나머지) 비교에 적합합니다.

### 강의 포인트
- 이 데이터셋은 집단 간 차이가 매우 커서 p-값이 극도로 작게 나옵니다.
  "통계적 유의성 ≠ 실질적 중요성" 논의에 효과 크기(Cohen's d, eta²)를 도입하기 좋습니다.
- ANOVA의 가정(정규성, 등분산성)을 Levene 검정과 Shapiro-Wilk 검정으로 점검하는
  절차를 시연하기에 적합합니다.
