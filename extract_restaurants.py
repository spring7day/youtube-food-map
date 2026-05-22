#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re

def extract_restaurants(description_text, video_id):
    """
    description 텍스트에서 식당 정보 추출
    반환: (video_title, main_area, restaurants 리스트)
    """
    lines = description_text.strip().split('\n')

    video_title = ""
    main_area = ""
    restaurants = []

    # 주요 도시/지역명 목록
    major_areas = [
        '종로', '군산', '강릉', '일산', '은평', '연신내', '청량리', '충정로',
        '광화문', '상주', '영주', '경주', '안동', '여수', '목포', '전주',
        '완주', '통영', '거제', '홍제', '홍제동', '서촌', '경복궁', '혜화',
        '무교', '광장시장', '남산', '안국', '강서구', '남山골'
    ]

    # 1단계: 제목 추출
    for i in range(min(5, len(lines))):
        line = lines[i].strip()
        if not line or line.startswith('http') or line.startswith('#'):
            continue
        if '맛집' in line and len(line) < 100:
            video_title = line
            break

    # 2단계: 지역 추출
    if video_title:
        title_words = video_title.split()
        for i, word in enumerate(title_words):
            if word == '맛집':
                if i > 0:
                    main_area = title_words[i-1]
                    # "서울 종로" 같은 두 단어 조합
                    if i > 1 and title_words[i-2] not in ['의', '가']:
                        potential = title_words[i-2]
                        if any(city in potential for city in ['서울', '경기', '강원', '인천', '대구', '부산', '대전', '광주']):
                            main_area = potential + ' ' + main_area
                break

    # 제목에서 못 찾으면 본문에서 찾기
    if not main_area:
        for line in lines[:15]:
            line_str = line.strip()
            for area in major_areas:
                if area in line_str:
                    main_area = area
                    break
            if main_area:
                break

    # 3단계: 타임스탬프 기반 식당명 추출
    for line in lines:
        line = line.strip()

        if not line:
            continue

        # URL, 해시태그, 이모지, 주소 줄 무시
        if line.startswith('http') or line.startswith('#') or line.startswith('👑'):
            continue

        if line.startswith('*') and not re.match(r'^\*[^\n]*맛집', line):
            continue

        # 타임스탬프 + 식당명 패턴
        timestamp_match = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?\s+(.+)$', line)
        if timestamp_match:
            restaurant_name = timestamp_match.group(4).strip()

            # 너무 짧으면 스킵
            if len(restaurant_name) < 2:
                continue

            # 숫자로만 이루어져 있으면 스킵
            if restaurant_name.replace(' ', '').replace(':', '').replace(',', '').isdigit():
                continue

            # 비식당/섹션 항목 필터링
            skip_keywords = [
                '인트로', 'intro', '미리보기', 'preview',
                '아웃트로', 'outro', '마치며', '완',
                '정보', '표', '소개', '다녀온', '목적지',
                '기념관', '도서관', '박물관', '역사',
                '감사', '링크', 'bgm', '출처', 'music',
            ]

            if any(keyword in restaurant_name.lower() for keyword in skip_keywords):
                continue

            # 역/동/구만 있는 정보성 항목 필터
            if re.match(r'^[가-힣]+역$', restaurant_name) or re.match(r'^[가-힣]+동$', restaurant_name) or re.match(r'^[가-힣]+구$', restaurant_name):
                continue

            # "/역" "/동" "/구" 같이 슬래시가 있는 지역정보만 필터
            if '/' in restaurant_name:
                parts = restaurant_name.split('/')
                if all(p.endswith('역') or p.endswith('동') or p.endswith('구') for p in parts if p.strip()):
                    continue

            # 한글/영문이 최소 하나는 있어야 함
            has_alpha = any(c.isalpha() or '가' <= c <= '힣' for c in restaurant_name)
            if not has_alpha:
                continue

            restaurants.append({
                "name": restaurant_name,
                "sub_area": main_area
            })

    return video_title, main_area, restaurants


def process_batch(batch_file_path, descriptions_dir, output_file_path):
    """
    배치 파일의 모든 비디오 ID를 처리하고 JSON으로 저장
    """
    results = []

    with open(batch_file_path, 'r', encoding='utf-8') as f:
        video_ids = [line.strip() for line in f if line.strip()]

    for video_id in video_ids:
        description_path = os.path.join(descriptions_dir, f'{video_id}.description')

        if not os.path.exists(description_path):
            print(f"⚠️  {video_id}.description not found")
            continue

        try:
            with open(description_path, 'r', encoding='utf-8') as f:
                description_text = f.read()

            video_title, main_area, restaurants = extract_restaurants(description_text, video_id)

            results.append({
                "video_id": video_id,
                "video_title": video_title,
                "main_area": main_area,
                "restaurants": restaurants
            })

            print(f"✓ {video_id}: {len(restaurants)} restaurants")

        except Exception as e:
            print(f"✗ {video_id}: {str(e)}")

    # 결과를 JSON으로 저장
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Results saved to {output_file_path}")
    print(f"Total: {len(results)} videos processed")


if __name__ == '__main__':
    batch_file = '/Users/jimin/Workspace/youtube-food-map/batches/batch_ab'
    descriptions_dir = '/Users/jimin/Workspace/youtube-food-map/descriptions'
    output_file = '/Users/jimin/Workspace/youtube-food-map/output/batch_ab.json'

    process_batch(batch_file, descriptions_dir, output_file)
