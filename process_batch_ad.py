#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re

def extract_info(description_text):
    """
    description에서 제목, 지역, 식당 정보 추출
    """
    lines = description_text.strip().split('\n')

    video_title = ""
    main_area = ""
    restaurants = []

    # 1단계: 제목 추출 (첫 10줄에서 "맛집" 포함)
    for line in lines[:10]:
        line = line.strip()
        if not line or line.startswith('http') or line.startswith('#'):
            continue
        if '맛집' in line and len(line) > 5 and len(line) < 100:
            video_title = line
            break

    # 제목이 없으면 첫 번째 유의미한 줄
    if not video_title:
        for line in lines[:10]:
            line = line.strip()
            if line and not line.startswith('http') and not line.startswith('#') and len(line) > 5:
                video_title = line
                break

    # 2단계: 지역 추출 (첫 10줄에서)
    # 지역명 목록
    cities = ['종로', '군산', '강릉', '일산', '은평', '연신내', '청량리', '광화문',
              '서울역', '안국역', '광장시장', '대구', '부산', '서울', '중구']

    for line in lines[:10]:
        for city in cities:
            if city in line:
                main_area = city
                break
        if main_area:
            break

    # 3단계: 타임스탬프 기반 식당 추출
    for line in lines:
        line = line.strip()

        if not line:
            continue

        # URL, 해시태그 등 무시
        if line.startswith('http') or line.startswith('#') or line.startswith('•'):
            continue

        # 타임스탬프 + 식당명 패턴
        match = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?\s+(.+)$', line)
        if match:
            name = match.group(4).strip()

            # 비식당 항목 제외
            skip = ['intro', 'preview', '인트로', '프리뷰', '마치며', '정보', '표', '소개',
                    '기념관', '도서관', '박물관', '맛집', '감사', 'BGM', '출처']

            if any(s.lower() in name.lower() for s in skip):
                continue

            # 너무 짧으면 제외
            if len(name) < 2:
                continue

            # 한글/영문 확인
            if not any(c.isalpha() or '가' <= c <= '힣' for c in name):
                continue

            restaurants.append({
                "name": name,
                "sub_area": main_area if main_area else ""
            })

    return video_title, main_area, restaurants


def main():
    batch_file = '/Users/jimin/Workspace/youtube-food-map/batches/batch_ad'
    descriptions_dir = '/Users/jimin/Workspace/youtube-food-map/descriptions'
    output_file = '/Users/jimin/Workspace/youtube-food-map/output/batch_ad.json'

    results = []

    # 배치 파일 읽기
    with open(batch_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    video_ids = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            video_ids.append(parts[1])
        else:
            video_ids.append(line)

    # 각 비디오 처리
    for video_id in video_ids:
        if not video_id:
            continue

        desc_path = os.path.join(descriptions_dir, f'{video_id}.description')

        if not os.path.exists(desc_path):
            print(f"⚠️  {video_id}.description not found")
            continue

        try:
            with open(desc_path, 'r', encoding='utf-8') as f:
                desc_text = f.read()

            title, area, rest = extract_info(desc_text)

            results.append({
                "video_id": video_id,
                "video_title": title,
                "main_area": area,
                "restaurants": rest
            })

            print(f"✓ {video_id}: {len(rest)} restaurants")

        except Exception as e:
            print(f"✗ {video_id}: {str(e)}")

    # 결과 저장
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Results saved to {output_file}")
    print(f"Total: {len(results)} videos processed")


if __name__ == '__main__':
    main()
