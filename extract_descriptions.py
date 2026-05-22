#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path

def extract_restaurants_from_description(content, video_id):
    """
    Description에서 식당 정보를 추출합니다.

    형식:
    1. "다녀온 곳은 [지역]" 패턴에서 main_area 추출
    2. "소개할 "[지역]"" 패턴에서 main_area 추출
    3. 타임스탐프: HH:MM 식당명에서 식당 추출
    4. 지역명/섹션명/비식당 키워드 제외
    """
    lines = content.strip().split('\n')

    restaurants = []
    video_title = ""
    main_area = ""

    # 비식당/섹션 키워드
    non_restaurant_keywords = {
        "preview", "preivew", "미리보기", "마치며", "intro", "인트로",
        "오프닝", "엔딩", "마감", "광고", "링크", "정보", "추가", "안내",
        "bgm", "출처", "제공", "track", "music", "다녀온 곳", "다녀온곳",
        "안녕하세요", "이번주", "이번 주", "백년해방",
        "토시살 리뷰", "메뉴별 추천", "느낀점", "꿀팁", "마무리",
        "순두부 추천", "장칼국수 추천", "리뷰", "선조들의지혜",
        "걸어온 길", "가지역", "짜장면 맛집", "소울푸드"
    }

    # 첫 번째 패스: 지역 정보 추출
    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # "이번 주 맛집 소개할 동네는 "[지역]"입니다" 패턴
        if "소개할 동네는" in line_stripped:
            # "이번 주 맛집 소개할 동네는 "을지로"입니다" -> "을지로"
            match = re.search(r'소개할 동네는\s*["\']?([^입니다"\']+)["\']?입니다', line_stripped)
            if match:
                main_area = match.group(1).strip().strip('"\'')

        # "다녀온 곳은 [지역]입니다" 패턴
        elif "다녀온 곳은" in line_stripped and "정보" not in line_stripped:
            # "다녀온 곳은 은평구입니다" -> "은평구"
            # "다녀온 곳은 "광화문"입니다" -> "광화문"
            match = re.search(r'다녀온 곳은\s*["\']?([^입니다"\']+)["\']?입니다', line_stripped)
            if match:
                main_area = match.group(1).strip().strip('"\'')

        # "이번주 맛집 소개를 위해 다녀온 곳은 [지역]입니다"
        elif "이번 주 맛집 소개를 위해" in line_stripped and "다녀온 곳은" in line_stripped:
            match = re.search(r'다녀온 곳은\s*["\']?([^입니다"\']+)["\']?입니다', line_stripped)
            if match:
                main_area = match.group(1).strip().strip('"\'')

        # "이번주 다녀온 곳은" 또는 "이번주 다녀온 곳" (다음 줄에 지역)
        elif ("이번주 다녀온 곳은" in line_stripped or "이번주 다녀온 곳" in line_stripped) and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # 다음 줄에 지역이 있을 수 있음
            if next_line and not any(x in next_line for x in ['http', '://', '#', '짧아진', '해당']):
                # "덕수궁 주변 맛집들 입니다" -> "덕수궁"
                area_match = re.match(r'^([^\s주변부근입니다]+)(?:\s|주변|부근)', next_line)
                if area_match:
                    main_area = area_match.group(1).strip()

        # "아래는 다녀온 [지역]\n맛집 정보 입니다" 패턴
        elif "아래는 다녀온" in line_stripped and i + 1 < len(lines):
            # "아래는 다녀온 파주 문산" -> "파주 문산"
            match = re.search(r'아래는 다녀온\s+(.+?)(?:\n|$)', line_stripped)
            if match:
                potential_area = match.group(1).strip()
                # 다음 줄이 "맛집 정보"로 시작하면 확인
                next_line = lines[i + 1].strip()
                if "맛집 정보" in next_line:
                    main_area = potential_area

    # 두 번째 패스: 타임스탐프에서 식당 추출
    seen_restaurants = set()  # 중복 제거용

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # 링크, 해시태그 줄 제외
        if any(x in line_stripped for x in ['http', '://', '#', '🎵', '브금', 'Music', 'Track', 'BGM']):
            continue

        # 주소 정보 줄 제외 (- 서울 종로구 ...)
        if re.match(r'^\-\s+서울|^\-\s+[0-9]', line_stripped):
            continue

        # 타임스탐프 형식: "00:00 항목명"
        match = re.match(r'^(\d{1,2}):(\d{2})\s+(.+)$', line_stripped)
        if match:
            item_name = match.group(3).strip()

            # 비식당 키워드 체크
            is_non_restaurant = any(
                kw.lower() in item_name.lower() for kw in non_restaurant_keywords
            )

            if is_non_restaurant:
                continue

            # 시간 정보 ("오전10시30분", "오후4시" 등) 제외
            if re.match(r'^(오전|오후|아침|점심|저녁|밤)\d', item_name):
                continue

            # 지역명 제외
            # main_area와 동일하거나 공백을 포함하는 경우 (예: "파주 문산", "강릉" 등)
            # 또는 "구"/"도"로 끝나는 경우
            if item_name == main_area:
                continue
            if re.search(r'(구|도)$', item_name):
                continue
            # "00:25 파주문산"처럼 타임스탐프 뒤 첫번째가 main_area의 일부일 가능성
            if main_area:
                # main_area와 동일하거나, main_area의 공백을 제거한 버전과 동일한 경우
                main_area_no_space = main_area.replace(' ', '')
                if item_name in main_area or item_name == main_area_no_space:
                    continue

            # 중복 제외
            if item_name not in seen_restaurants:
                restaurants.append({
                    "name": item_name,
                    "sub_area": main_area
                })
                seen_restaurants.add(item_name)

        # 숫자. 형식 식당 (1.박가삼거리부대찌개)
        elif re.match(r'^\d+\.\s*\S', line_stripped):
            restaurant_name = re.sub(r'^\d+\.\s*', '', line_stripped).strip()

            if restaurant_name and len(restaurant_name) > 1:
                is_non_restaurant = any(
                    kw.lower() in restaurant_name.lower() for kw in non_restaurant_keywords
                )
                if not is_non_restaurant and restaurant_name not in seen_restaurants:
                    restaurants.append({
                        "name": restaurant_name,
                        "sub_area": main_area
                    })
                    seen_restaurants.add(restaurant_name)

    return {
        "video_id": video_id,
        "video_title": video_title,
        "main_area": main_area,
        "restaurants": restaurants
    }

def process_batch():
    """batch_ac 파일의 모든 영상 ID를 처리합니다."""
    batch_path = "/Users/jimin/Workspace/youtube-food-map/batches/batch_ac"
    desc_dir = "/Users/jimin/Workspace/youtube-food-map/descriptions"
    output_path = "/Users/jimin/Workspace/youtube-food-map/output/batch_ac.json"

    results = []

    with open(batch_path, 'r') as f:
        for line in f:
            video_id = line.strip()
            if not video_id:  # 빈 줄 제외
                continue

            desc_file = os.path.join(desc_dir, f"{video_id}.description")

            if os.path.exists(desc_file):
                with open(desc_file, 'r', encoding='utf-8') as df:
                    content = df.read()
                    result = extract_restaurants_from_description(content, video_id)
                    results.append(result)
            else:
                print(f"파일 없음: {desc_file}")

    # JSON으로 저장
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"완료: {output_path}")
    print(f"처리된 영상 수: {len(results)}")

if __name__ == "__main__":
    process_batch()
