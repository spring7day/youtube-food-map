# 백년해방 맛집 지도

유튜브 채널 [백년해방](https://youtube.com/channel/UCSW_W-SE71e9OhZwPEkEDLA)에 소개된 481개 맛집을 지도에 표시한 모바일 친화적 single-file HTML.

## 데모
👉 https://spring7day.github.io/youtube-food-map/

## 기능
- Leaflet + OSM 타일 기반 인터랙티브 지도
- 마커 클러스터링
- 광역(구) 단위 필터 칩
- 식당명/지역 실시간 검색
- 현재 위치 기반 주변 맛집
- 마커 클릭 시 상세 정보 + 유튜브 영상 링크

## 데이터
- 카카오맵 검색으로 좌표 매핑
- 외부 교차 검증 (15개 샘플, 93.3% 통과)
- 481개 식당 (서울/경기/강원/전북/대전)

## 파이프라인
1. yt-dlp로 80개 영상 description 추출
2. Haiku 모델 4개 병렬로 식당명 파싱 (565개)
3. 카카오맵 비공식 검색 API로 좌표 매핑
4. Sonnet 모델로 의심 매칭 검증
5. 외부 소스 교차 검증
