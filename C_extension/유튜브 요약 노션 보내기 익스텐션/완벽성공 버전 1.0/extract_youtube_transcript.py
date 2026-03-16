#!/usr/bin/env python3
# extract_youtube_transcript.py

import sys
import json
from youtube_transcript_api import YouTubeTranscriptApi

def extract_video_id(url):
    """YouTube URL에서 video_id 추출"""
    if 'v=' in url:
        return url.split('v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    return None

def fetch_transcript(video_id, language="ko"):
    """유튜브 자막 추출"""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = None
        
        # 1. 한국어 수동 자막
        try:
            transcript = transcript_list.find_transcript([language])
        except:
            # 2. 한국어 자동 자막
            try:
                transcript = transcript_list.find_generated_transcript([language])
            except:
                # 3. 첫 번째 사용 가능한 자막
                try:
                    transcript = next(iter(transcript_list))
                except:
                    return None
        
        # 자막 텍스트 추출
        transcript_data = transcript.fetch()
        text_list = []
        for entry in transcript_data:
            if hasattr(entry, 'text'):
                if entry.text:
                    text_list.append(entry.text)
            elif isinstance(entry, dict) and 'text' in entry:
                text_list.append(entry['text'])
        
        return ' '.join(text_list)
    except Exception as e:
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "YouTube URL이 필요합니다"}))
        sys.exit(1)
    
    youtube_url = sys.argv[1]
    video_id = extract_video_id(youtube_url)
    
    if not video_id:
        print(json.dumps({"error": "잘못된 YouTube URL입니다"}))
        sys.exit(1)
    
    transcript = fetch_transcript(video_id)
    
    if transcript:
        print(json.dumps({
            "success": True,
            "video_id": video_id,
            "transcript": transcript
        }, ensure_ascii=False))
    else:
        print(json.dumps({
            "success": False,
            "error": "자막을 찾을 수 없습니다"
        }, ensure_ascii=False))