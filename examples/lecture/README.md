# oh_my_research 강의 예제 데이터셋

이 폴더는 "챗지피티를 이용한 데이터 분석" (WikiDocs §3.1) 강의에서
oh_my_research MVP 통계 워크플로를 실습하기 위한 UCI 공개 데이터셋 4종을 담고 있습니다.

---

## 데이터셋 인덱스

| 데이터셋 | 폴더 | 행수 | 추천 분석 | 가이드 |
|----------|------|------|-----------|--------|
| Iris Plants Database | `iris/` | 150 | 일원 ANOVA (petal_length ~ species), 독립표본 t-검정 | [iris/lecture-guide.md](iris/lecture-guide.md) |
| Wine Quality (Red) | `wine-quality-red/` | 1,599 | 단순 OLS 회귀 (quality ~ alcohol), 회귀 가정점검 | [wine-quality-red/lecture-guide.md](wine-quality-red/lecture-guide.md) |
| Auto MPG | `auto-mpg/` | 398 | OLS 회귀 (mpg ~ weight), 결측값 blocked-pending 시연 | [auto-mpg/lecture-guide.md](auto-mpg/lecture-guide.md) |
| Breast Cancer WDBC | `breast-cancer-wdbc/` | 569 | 독립표본 t-검정 (radius_mean ~ diagnosis), χ² 검정 | [breast-cancer-wdbc/lecture-guide.md](breast-cancer-wdbc/lecture-guide.md) |

---

## 한 줄 사용법

1. **워크스페이스 폴더 열기:** oh_my_research에서 새 분석 워크스페이스를 만듭니다.

2. **데이터 복사:** 원하는 데이터셋의 `data.csv`를 워크스페이스의 `20_analysis/data/` 폴더에 복사합니다.
   ```
   예: iris/data.csv → <워크스페이스>/20_analysis/data/data.csv
   ```

3. **분석 시작:**
   ```
   $omr-start  세 붓꽃 품종의 꽃잎 길이(petal_length) 차이를 일원 ANOVA로 분석해 주세요.
   ```

4. **분석 실행:**
   ```
   $omr-analyze  petal_length ~ species로 one-way ANOVA를 수행해 주세요.
   ```

5. **결과 확인:** `results.json`의 `statistic`, `p_value`, `label` 필드를 확인합니다.

---

## 폴더 구조

```
examples/lecture/
├── README.md                      ← 이 파일
├── iris/
│   ├── data.csv                   ← 150행, 헤더 포함, comma-separated
│   ├── data-dictionary.md
│   ├── lecture-guide.md
│   └── SOURCE.md
├── wine-quality-red/
│   ├── data.csv                   ← 1599행, 헤더 포함, comma-separated (원본 ';' 변환)
│   ├── data-dictionary.md
│   ├── lecture-guide.md
│   └── SOURCE.md
├── auto-mpg/
│   ├── data.csv                   ← 398행, 헤더 포함, horsepower 결측=빈 셀 6개
│   ├── data-dictionary.md
│   ├── lecture-guide.md
│   └── SOURCE.md
└── breast-cancer-wdbc/
    ├── data.csv                   ← 569행, 32컬럼 헤더 포함
    ├── data-dictionary.md
    ├── lecture-guide.md
    └── SOURCE.md
```

---

## 출처

모든 데이터셋은 UCI Machine Learning Repository에서 공개된 학술/교육용 공개 데이터입니다.
각 데이터셋 폴더의 `SOURCE.md`에서 원본 URL, 인용 정보, 다운로드 일자를 확인할 수 있습니다.

Dua, D. and Graff, C. (2019). UCI Machine Learning Repository [http://archive.ics.uci.edu/ml].
Irvine, CA: University of California, School of Information and Computer Science.
