#!/usr/bin/env python3
import json
import os
import time
from typing import Dict, List, Set
import requests
from tqdm import tqdm
import click

class JenkinsPluginDownloader:
    UPDATE_CENTER_URL = "https://updates.jenkins.io/update-center.json"
    MIRROR_URLS = [
        "https://mirrors.tuna.tsinghua.edu.cn/jenkins/plugins",
        "https://mirrors.aliyun.com/jenkins/plugins",
        "https://updates.jenkins.io/download/plugins",
        "https://mirrors.jenkins.io/plugins",
    ]
    
    def __init__(self, output_dir: str = "plugins"):
        self.output_dir = output_dir
        self.plugins_data = {}
        self.downloaded_plugins: Set[str] = set()
        self.current_mirror_index = 0
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def fetch_update_center(self) -> None:
        """Jenkins Update Center에서 플러그인 정보를 가져옵니다."""
        response = requests.get(self.UPDATE_CENTER_URL)
        # JSON 문자열에서 실제 JSON 부분만 추출
        json_str = response.text.split("updateCenter.post(")[1].rstrip(");")
        self.plugins_data = json.loads(json_str)["plugins"]
    
    def get_plugin_dependencies(self, plugin_name: str) -> List[str]:
        """플러그인의 의존성을 재귀적으로 가져옵니다."""
        if plugin_name not in self.plugins_data:
            return []
        
        dependencies = []
        plugin = self.plugins_data[plugin_name]
        
        if "dependencies" in plugin:
            for dep in plugin["dependencies"]:
                if dep.get("optional", False):
                    continue
                dep_name = dep["name"]
                dependencies.append(dep_name)
                dependencies.extend(self.get_plugin_dependencies(dep_name))
        
        return list(set(dependencies))
    
    def download_plugin(self, plugin_name: str, version: str = None) -> None:
        """플러그인과 그 의존성을 다운로드합니다."""
        if not self.plugins_data:
            self.fetch_update_center()
        
        if plugin_name not in self.plugins_data:
            raise ValueError(f"Plugin {plugin_name} not found in update center")
        
        plugin = self.plugins_data[plugin_name]
        if version is None:
            version = plugin["version"]
        
        # 의존성 플러그인 목록 생성
        dependencies = self.get_plugin_dependencies(plugin_name)
        all_plugins = [plugin_name] + dependencies
        
        click.echo(f"\n다운로드할 플러그인 목록:")
        click.echo(f"- {plugin_name} (메인 플러그인)")
        for dep in dependencies:
            click.echo(f"- {dep} (의존성)")
        click.echo(f"\n총 {len(all_plugins)}개 플러그인 다운로드 시작...\n")
        
        # 전체 진행 상황 표시
        with tqdm(total=len(all_plugins), desc="전체 진행률", position=0) as pbar:
            # 의존성 플러그인 다운로드
            for dep in dependencies:
                if dep not in self.downloaded_plugins:
                    self._download_single_plugin(dep)
                pbar.update(1)
            
            # 메인 플러그인 다운로드
            if plugin_name not in self.downloaded_plugins:
                self._download_single_plugin(plugin_name, version)
                pbar.update(1)
    
    def _get_download_url(self, plugin_name: str, version: str) -> str:
        """현재 미러 사이트의 다운로드 URL을 반환합니다."""
        base_url = self.MIRROR_URLS[self.current_mirror_index]
        return f"{base_url}/{plugin_name}/{version}/{plugin_name}.hpi"
    
    def _try_next_mirror(self) -> bool:
        """다음 미러 사이트로 전환합니다."""
        self.current_mirror_index = (self.current_mirror_index + 1) % len(self.MIRROR_URLS)
        return self.current_mirror_index != 0  # 모든 미러를 시도했는지 확인
    
    def _download_single_plugin(self, plugin_name: str, version: str = None) -> None:
        """단일 플러그인을 다운로드합니다."""
        if plugin_name in self.downloaded_plugins:
            return
        
        plugin = self.plugins_data[plugin_name]
        if version is None:
            version = plugin["version"]
        
        output_path = os.path.join(self.output_dir, f"{plugin_name}.hpi")
        
        while True:
            try:
                download_url = self._get_download_url(plugin_name, version)
                response = requests.get(download_url, stream=True)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                start_time = time.time()
                last_speed_check = start_time
                last_downloaded = 0
                
                with open(output_path, 'wb') as f, tqdm(
                    desc=f"Downloading {plugin_name} from {self.MIRROR_URLS[self.current_mirror_index]}",
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    position=1,
                    leave=False
                ) as pbar:
                    for data in response.iter_content(chunk_size=1024):
                        current_time = time.time()
                        downloaded_size += len(data)
                        f.write(data)
                        pbar.update(len(data))
                        
                        # 1초마다 속도 체크
                        if current_time - last_speed_check >= 1.0:
                            speed = (downloaded_size - last_downloaded) / (current_time - last_speed_check)
                            if speed < 1024:  # 1KB/s 미만
                                click.echo(f"\n다운로드 속도가 느립니다 ({speed:.2f} B/s). 다른 미러로 전환합니다...")
                                if not self._try_next_mirror():
                                    raise Exception("모든 미러 사이트에서 다운로드 실패")
                                break
                            last_speed_check = current_time
                            last_downloaded = downloaded_size
                
                if downloaded_size == total_size:
                    break
                    
            except Exception as e:
                click.echo(f"\n다운로드 실패: {str(e)}")
                if not self._try_next_mirror():
                    raise Exception("모든 미러 사이트에서 다운로드 실패")
        
        self.downloaded_plugins.add(plugin_name)

@click.command()
@click.argument('plugin_name')
@click.option('--version', '-v', help='플러그인 버전 (지정하지 않으면 최신 버전 사용)')
@click.option('--output-dir', '-o', default='plugins', help='다운로드할 디렉토리 (기본값: plugins)')
def main(plugin_name: str, version: str, output_dir: str):
    """Jenkins 플러그인과 의존성을 다운로드합니다."""
    try:
        downloader = JenkinsPluginDownloader(output_dir)
        downloader.download_plugin(plugin_name, version)
        click.echo(f"\n플러그인 다운로드 완료: {plugin_name}")
        click.echo(f"다운로드 위치: {os.path.abspath(output_dir)}")
    except Exception as e:
        click.echo(f"오류 발생: {str(e)}", err=True)
        exit(1)

if __name__ == '__main__':
    main() 