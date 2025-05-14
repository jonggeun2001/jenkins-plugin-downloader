# Jenkins Plugin Downloader

Jenkins 플러그인과 그 의존성을 다운로드하는 CLI 도구입니다.

## 설치

```bash
pip install -r requirements.txt
```

## 사용 방법

```bash
# 기본 사용법 (최신 버전 다운로드)
python jenkins_plugin_downloader.py git

# 특정 버전 다운로드
python jenkins_plugin_downloader.py git --version 4.11.0

# 다운로드 디렉토리 지정
python jenkins_plugin_downloader.py git --output-dir my_plugins
```

## 옵션

- `plugin_name`: 다운로드할 플러그인 이름 (필수)
- `--version`, `-v`: 플러그인 버전 (선택, 기본값: 최신 버전)
- `--output-dir`, `-o`: 다운로드 디렉토리 (선택, 기본값: plugins)