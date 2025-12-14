# PMPDP - Portable MPD Player

Raspberry Pi Zero 2 W と Pirate Audio HAT を使用した、MPD (Music Player Daemon) ベースのポータブル音楽プレイヤーです。ST7789ディスプレイを使用したGUIインターフェースを提供します。

## ハードウェア要件

- **Raspberry Pi Zero 2 W**
- **[Pirate Audio Headphone Amp](https://shop.pimoroni.com/products/pirate-audio-headphone-amp?variant=31189750480979)**
  - 240x240 ST7789 ディスプレイ
  - 4つの物理ボタン (GPIO 5, 6, 16, 20)
  - I2S オーディオ出力

## ソフトウェア要件

- **OS**: DietPi 13 (Trike) または Raspberry Pi OS
- **Python**: 3.x
- **MPD** (Music Player Daemon)

### 必要なPythonパッケージ

```bash
pip3 install st7789 gpiozero pillow python-mpd2
```

## 機能

### 主要機能

- **ライブラリブラウザ**: MPD音楽ライブラリの閲覧
- **再生コントロール**: 再生/一時停止、音量調整
- **再生キュー管理**: キューの表示、曲の移動・削除
- **アルバムアート表示**: 埋め込みアートワークの表示
- **システム管理**: WiFi切替、シャットダウン、再起動

### ボタン操作

| ボタン | GPIO | 機能 |
|--------|------|------|
| アクション | 5 | 決定/再生・停止 |
| 戻る | 6 | 前の画面に戻る |
| 上 | 16 | カーソル上移動/音量アップ |
| 下 | 20 | カーソル下移動/音量ダウン |

### 画面構成

1. **メインメニュー**
   - ライブラリ
   - 再生中
   - 再生キュー
   - シャットダウン
   - 再起動
   - 消灯
   - WiFi切替

2. **ライブラリ画面**
   - フォルダ/ファイル/プレイリストの閲覧
   - アクションメニュー（今すぐ再生、キューに追加、次に割込追加）

3. **再生中画面**
   - アルバムアート表示
   - 曲情報（タイトル、アーティスト）
   - 再生時間/総時間
   - 再生状態

4. **再生キュー画面**
   - シャッフル/リピート設定
   - キュー内の曲一覧
   - 曲の移動・削除

## インストール

### 1. システムパッケージのインストール

```bash
# MPDのインストール
sudo apt-get update
sudo apt-get install mpd mpc

# 必要なライブラリのインストール
sudo apt-get install python3-pip python3-pil python3-numpy
```

### 2. Pythonパッケージのインストール

```bash
pip3 install --break-system-packages st7789 gpiozero pillow python-mpd2
```

### 3. プロジェクトファイルの配置

```bash
# プロジェクトディレクトリの作成
sudo mkdir -p /opt/pmpdp/bin
sudo mkdir -p /opt/pmpdp/misaki

# ファイルのコピー
sudo cp pmpdp2.py /opt/pmpdp/
sudo cp runme.sh /opt/pmpdp/
sudo chmod +x /opt/pmpdp/runme.sh

# フォントファイルの配置
# misaki_gothic.ttf を /opt/pmpdp/misaki/ に配置してください
```

### 4. MPDの設定

`/etc/mpd.conf` を編集してください:

```conf
music_directory    "/var/lib/mpd/music"
playlist_directory "/var/lib/mpd/playlists"

bind_to_address "localhost"
port "6600"

# I2S オーディオ出力の設定
audio_output {
    type        "alsa"
    name        "Pirate Audio"
    device      "hw:0,0"
    mixer_type  "software"
}
```

音楽ファイルを `/var/lib/mpd/music/` に配置し、データベースを更新:

```bash
sudo systemctl restart mpd
mpc update
```

### 5. systemdサービスの設定（オプション）

自動起動を設定する場合:

```bash
sudo nano /etc/systemd/system/pmpdp.service
```

```ini
[Unit]
Description=Portable MPD Player
After=mpd.service network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/pmpdp
ExecStart=/opt/pmpdp/runme.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

サービスの有効化:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pmpdp.service
sudo systemctl start pmpdp.service
```

## 使用方法

### 手動起動

```bash
cd /opt/pmpdp
./runme.sh
```

### 基本操作

1. **メインメニュー**から「ライブラリ」を選択
2. 曲またはフォルダを選択してアクションボタンを押す
3. アクションメニューから操作を選択
   - 今すぐ再生
   - キューの最後に追加
   - 次に割込追加

4. **再生中画面**でアクションボタンを押すと再生/停止を切り替え
5. 上下ボタンで音量調整

### WiFi管理

メインメニューから「WiFi」を選択すると、WiFiのON/OFF切替が可能です。

### 省電力機能

メインメニューから「消灯」を選択すると、ディスプレイのバックライトが消灯します。任意のボタンを押すと再点灯します。

## トラブルシューティング

### MPDに接続できない

```bash
# MPDの状態を確認
sudo systemctl status mpd

# MPDを再起動
sudo systemctl restart mpd
```

### ディスプレイが表示されない

- SPI が有効になっているか確認してください
- `sudo raspi-config` > Interfacing Options > SPI > Enable

### 音が出ない

- I2S オーディオデバイスが正しく設定されているか確認
- `aplay -l` でデバイス一覧を確認
- MPDの audio_output 設定を確認

### フォントが表示されない

- 美咲ゴシックフォント (misaki_gothic.ttf) が `/opt/pmpdp/misaki/` に配置されているか確認
- フォントは[こちら](https://littlelimit.net/misaki.htm)からダウンロード可能

## 依存関係

- **st7789**: ST7789ディスプレイドライバ
- **gpiozero**: GPIOボタン制御
- **PIL (Pillow)**: 画像処理・描画
- **python-mpd2**: MPDクライアントライブラリ

## ライセンス

このプロジェクトは個人利用を目的としています。

## 謝辞

- [Pimoroni](https://shop.pimoroni.com/) - Pirate Audio HAT
- [MPD](https://www.musicpd.org/) - Music Player Daemon
- [美咲フォント](https://littlelimit.net/misaki.htm) - 日本語フォント

## 更新履歴

- **v2.0**: MPD接続のキープアライブ機能追加、安定性向上
- **v1.0**: 初回リリース
