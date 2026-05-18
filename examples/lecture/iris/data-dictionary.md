# 데이터 사전: Iris Plants Database

**행 수:** 150행 (데이터), 1행 헤더  
**출처:** UCI ML Repository — Fisher's Iris Dataset (1936)

---

## 변수 목록

### sepal_length
- **타입:** 연속(continuous)
- **역할 후보:** 독립변수(예측변수)
- **측정 단위/범위:** 센티미터(cm), 4.3 ~ 7.9
- **결측 여부:** 없음

### sepal_width
- **타입:** 연속(continuous)
- **역할 후보:** 독립변수(예측변수)
- **측정 단위/범위:** 센티미터(cm), 2.0 ~ 4.4
- **결측 여부:** 없음

### petal_length
- **타입:** 연속(continuous)
- **역할 후보:** 독립변수(예측변수) — 품종 구별력 높음
- **측정 단위/범위:** 센티미터(cm), 1.0 ~ 6.9
- **결측 여부:** 없음

### petal_width
- **타입:** 연속(continuous)
- **역할 후보:** 독립변수(예측변수) — 품종 구별력 높음
- **측정 단위/범위:** 센티미터(cm), 0.1 ~ 2.5
- **결측 여부:** 없음

### species
- **타입:** 범주(categorical) — 명목
- **역할 후보:** 종속변수(집단 구분 변수), 분류 레이블
- **값:** Iris-setosa / Iris-versicolor / Iris-virginica (각 50행씩 균형)
- **결측 여부:** 없음

---

## 참고사항
- 세 품종이 각 50행으로 완전히 균형 잡혀 있어 ANOVA 및 t-검정 실습에 이상적입니다.
- petal_length와 petal_width는 품종 간 분리도가 높아 검정력이 강한 예시를 제공합니다.
- sepal_width는 품종 간 차이가 상대적으로 작아 Type II 오류 토론에 활용 가능합니다.
