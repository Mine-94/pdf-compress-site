# PDF압축

Ghostscript 기반으로 실제 PDF 용량을 줄여주는 Flask 웹앱입니다. Smallpdf, iLovePDF 같은 서비스와 동일한 방식(이미지 재압축)으로 동작합니다.

## 로컬에서 실행하기

Ghostscript가 설치되어 있어야 합니다.

```bash
# macOS
brew install ghostscript

# Ubuntu/Debian
sudo apt-get install ghostscript
```

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

브라우저에서 `http://localhost:5000` 접속.

## Docker로 실행하기

```bash
docker build -t pdf-compress .
docker run -p 8080:8080 pdf-compress
```

## 무료/저비용 배포 (Render 예시)

1. 이 폴더를 GitHub 저장소로 올립니다.
2. [render.com](https://render.com) 가입 → **New > Web Service** → 저장소 연결.
3. Environment는 **Docker**를 선택 (Dockerfile을 자동 인식합니다).
4. Region, Plan(Free 또는 Starter)을 선택하고 배포.
5. 배포가 끝나면 `https://your-app.onrender.com` 같은 주소가 생깁니다.

Railway, Fly.io도 Dockerfile을 그대로 인식하므로 동일한 방식으로 배포할 수 있습니다. (일반 PaaS 무료 티어에는 Ghostscript가 기본 설치되어 있지 않으므로, 반드시 Dockerfile 기반 배포를 사용하세요.)

## 도메인 연결 및 구글/네이버 등록

1. 배포 후 원하는 도메인을 구입하고(가비아, 후이즈 등), 호스팅 서비스의 커스텀 도메인 설정에 연결하세요.
2. `static/robots.txt`, `static/sitemap.xml` 안의 `your-domain.com`을 실제 도메인으로 바꾸세요.
3. **Google Search Console** → 속성 추가 → 소유권 확인 → 사이트맵(`/sitemap.xml`) 제출.
4. **네이버 서치어드바이저**(searchadvisor.naver.com) → 사이트 등록 → 사이트맵 제출.

## 구글 애드센스 연동

1. [google.com/adsense](https://www.google.com/adsense)에서 사이트 등록 후 심사를 신청하세요. (실제 트래픽과 개인정보처리방침/이용약관 페이지가 있어야 승인 확률이 높습니다. 이미 포함되어 있습니다.)
2. 승인 후 발급받는 `client=ca-pub-XXXXXXXXXXXXXXXX` 값을 `templates/base.html`의 주석 처리된 `<script>` 태그에 채우고 주석을 해제하세요.
3. `static/ads.txt` 파일에 애드센스가 안내하는 실제 publisher 정보를 입력하세요.
4. 광고 유닛 코드를 `templates/index.html`의 `<div class="ad-slot" id="ad-slot-below-tool"></div>` 안에 붙여넣으세요.

## 압축 품질 옵션

| 옵션 | Ghostscript 설정 | 용도 |
|---|---|---|
| 고화질 | `/printer` | 인쇄용, 압축률 낮음 |
| 권장 | `/ebook` | 일반 문서 공유용 (기본값) |
| 최대 압축 | `/screen` | 화면 보기 전용, 압축률 최대 |

## 파일 정책

- 업로드 최대 용량: 100MB
- 압축/다운로드 완료 후 서버에서 파일 자동 삭제
- 이미 최적화된 PDF의 경우 원본 그대로 반환

## 추가로 고려하면 좋은 것

- 트래픽이 늘면 임시 파일 정리를 위한 주기적 cron(오래된 파일 삭제) 추가
- 여러 파일 동시 처리(배치 압축), 파일 병합/분할 등 기능 확장
- Google Analytics 연동으로 방문자 추적
