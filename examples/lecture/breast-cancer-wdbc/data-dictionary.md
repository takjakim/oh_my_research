# 데이터 사전: Breast Cancer Wisconsin (Diagnostic) Dataset

**행 수:** 569행 (데이터), 1행 헤더  
**출처:** UCI ML Repository — Wolberg, Street, Mangasarian (1993)  
**컬럼 수:** 32 (id, diagnosis, 특징 30개)

---

## 식별자 변수

### id
- **타입:** 식별자(identifier)
- **역할 후보:** 행 레이블 (분석에서 제외)
- **측정 단위/범위:** 정수 환자 ID
- **결측 여부:** 없음

### diagnosis
- **타입:** 범주(categorical) — 이진
- **역할 후보:** 종속변수(분류 레이블), 집단 구분 변수
- **값:** M = 악성(Malignant, 212행), B = 양성(Benign, 357행)
- **결측 여부:** 없음

---

## 특징 변수 (30개)

세포핵 이미지에서 추출한 10가지 특성 × 3가지 통계량(_mean, _se, _worst)의 조합.

### 측정 특성 10종

| 특성명 | 설명 |
|--------|------|
| radius | 중심에서 경계점까지의 평균 거리 |
| texture | 회색조 값의 표준편차 |
| perimeter | 핵 경계의 둘레 |
| area | 핵의 면적 |
| smoothness | 반지름 길이의 국소 변화율 |
| compactness | perimeter² / area − 1.0 |
| concavity | 경계의 오목한 부분의 심도 |
| concave_points | 경계의 오목한 부분 수 |
| symmetry | 핵의 대칭성 |
| fractal_dimension | "해안선 근사" − 1 |

### 통계량 3종

| 접미사 | 의미 |
|--------|------|
| _mean | 슬라이드 내 세포핵 값의 평균 |
| _se | 표준오차(Standard Error) |
| _worst | 가장 큰 3개 값의 평균 (worst case) |

### 주요 변수 예시

#### radius_mean
- **타입:** 연속(continuous)
- **역할 후보:** 독립변수 — 집단 간 차이가 가장 큰 변수 중 하나
- **측정 단위/범위:** 마이크로미터(μm), 6.98 ~ 28.11
- **결측 여부:** 없음

#### concave_points_mean
- **타입:** 연속(continuous)
- **역할 후보:** 독립변수 — 악성 판별에 중요한 형태학적 지표
- **측정 단위/범위:** 0.0 ~ 0.2012 (무단위 비율)
- **결측 여부:** 없음

#### area_worst
- **타입:** 연속(continuous)
- **역할 후보:** 독립변수 — 최악 케이스 면적, 분류 성능에 기여
- **측정 단위/범위:** μm², 185.2 ~ 4254.0
- **결측 여부:** 없음

---

## 참고사항
- 모든 30개 특징 변수에 결측값이 없습니다.
- M(악성):B(양성) 비율 = 212:357 ≈ 37:63 (불균형 클래스, 통계 해석 시 주의).
- oh_my_research MVP 범위에서는 2집단 t-검정(radius_mean ~ diagnosis)과
  χ² 검정(진단 × 범주화 변수)까지 다룹니다. 로지스틱 회귀는 MVP 밖입니다.
