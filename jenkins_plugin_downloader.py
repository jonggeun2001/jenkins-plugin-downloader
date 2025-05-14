#!/usr/bin/env python3
import json
import os
from typing import Dict, List, Set
import requests
from tqdm import tqdm
import click

class JenkinsPluginDownloader:
    UPDATE_CENTER_URL = "https://updates.jenkins.io/update-center.json"
    
    def __init__(self, output_dir: str = "plugins"):
        self.output_dir = output_dir
        self.plugins_data = {}
        self.downloaded_plugins: Set[str] = set()
        
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
        
        # 의존성 플러그인 다운로드
        dependencies = self.get_plugin_dependencies(plugin_name)
        for dep in dependencies:
            if dep not in self.downloaded_plugins:
                self._download_single_plugin(dep)
        
        # 메인 플러그인 다운로드
        if plugin_name not in self.downloaded_plugins:
            self._download_single_plugin(plugin_name, version)
    
    def _download_single_plugin(self, plugin_name: str, version: str = None) -> None:
        """단일 플러그인을 다운로드합니다."""
        if plugin_name in self.downloaded_plugins:
            return
        
        plugin = self.plugins_data[plugin_name]
        if version is None:
            version = plugin["version"]
        
        download_url = f"https://updates.jenkins.io/download/plugins/{plugin_name}/{version}/{plugin_name}.hpi"
        output_path = os.path.join(self.output_dir, f"{plugin_name}.hpi")
        
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        with open(output_path, 'wb') as f, tqdm(
            desc=f"Downloading {plugin_name}",
            total=total_size,
            unit='iB',
            unit_scale=True
        ) as pbar:
            for data in response.iter_content(chunk_size=1024):
                size = f.write(data)
                pbar.update(size)
        
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