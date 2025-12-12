#!/usr/bin/env python3

import sys, threading, time, os, st7789, subprocess
from gpiozero import Button
from PIL import Image, ImageDraw, ImageFont
from mpd import MPDClient

#!!ATTENSION!! Older Pirate Audio using GPIO 20 insted of GPIO 24 for Y BUTTON (not witten in official documents).IF NOT WORKING, REPLACE ALL! !!ATTENSION!!

# ボタン設定（元のプロジェクトと同じピン配置）
button1 = Button(5)   # 決定ボタン
button2 = Button(6)   # 戻るボタン
button3 = Button(16)  # 上ボタン
button4 = Button(20)  # 下ボタン

# MPDクライアント設定
client = MPDClient()
client.timeout = 10
client.idletimeout = None
watch_client = MPDClient()
watch_client.timeout = 10 
# グローバル変数
pathes = []
files = []
selectedindex = 0
operation_mode = "main screen"
previous_operation_mode = "main_screen"
display_type = "square"
current_folder = ""
is_playing = False

def connect_mpd():
    """MPDサーバーに接続"""
    try:
        client.connect("localhost", 6600)
        watch_client.connect("localhost", 6600)
        print("Connected to MPD server")
        return True
    except Exception as e:
        print(f"Failed to connect to MPD: {e}")
        return False

def get_music_folders():
    """音楽フォルダのリストを取得"""
    try:
        folders = []
        items = client.lsinfo()
        for item in items:
            if 'directory' in item:
                folders.append(item['directory'])
        return folders
    except Exception as e:
        print(f"Error getting folders: {e}")
        return []


def keep_alive_loop():
    """メインクライアントの接続状態を定期的に確認し、切断されていたら再接続する"""
    global client
    # 30秒ごとに接続を確認
    interval = 5

    while True:
        try:
            # client.ping() は、接続が正常ならTrueを返すか何も返さない
            # 接続が切断されていれば例外(ConnectionError/ProtocolError)が発生する
            client.ping()
            # print("Main client ping successful.") # デバッグ用

        except Exception as e:
            # 接続エラーやソケットエラーが発生した場合
            print(f"Main client keep-alive failed: {e}. Attempting reconnect...")
            try:
                # 既存の接続を確実に切断
                client.disconnect()
            except:
                pass

            try:
                # 再接続
                client.connect("localhost", 6600)
                print("Main client successfully reconnected by keep-alive.")
            except Exception as re_e:
                print(f"Main client reconnection failed: {re_e}.")
                # 再接続に失敗した場合でも、次のループで再度試みる

        # 設定された間隔だけ待機
        time.sleep(interval)

def get_folder_contents(folder_path):
    """指定フォルダの内容を取得"""
    try:
        contents = []
        items = client.lsinfo(folder_path) if folder_path else client.lsinfo()
        
        for item in items:
            if 'directory' in item:
                dir_name = item['directory'].split('/')[-1]
                contents.append(('folder', item['directory'], f"[DIR] {dir_name}"))
            elif 'file' in item:
                # タイトルがあれば使用、なければファイル名
                if 'title' in item:
                    display_name = item['title']
                elif 'name' in item:
                    display_name = item['name']
                else:
                    display_name = item['file'].split('/')[-1]
                contents.append(('file', item['file'], display_name))
        
        return contents
    except Exception as e:
        print(f"Error getting folder contents: {e}")
        return []

def play_file(file_path):
    """ファイルを再生"""
    global is_playing
    try:
        client.clear()
        client.add(file_path)
        client.play(0)
        is_playing = True
        print(f"Playing: {file_path}")
    except Exception as e:
        print(f"Error playing file: {e}")

def play_folder(folder_path):
    """フォルダ全体を再生"""
    global is_playing
    try:
        client.clear()
        # フォルダ内のすべてのファイルを追加
        items = client.lsinfo(folder_path)
        for item in items:
            if 'file' in item:
                client.add(item['file'])
        client.play(0)
        is_playing = True
        print(f"Playing folder: {folder_path}")
    except Exception as e:
        print(f"Error playing folder: {e}")

def add_recursive_files(folder_path):
    """指定フォルダ以下のすべてのファイルをMPDキューに追加（再帰処理）"""
    try:
        items = client.lsinfo(folder_path) if folder_path else client.lsinfo()
        
        for item in items:
            if 'file' in item:
                client.add(item['file'])
            elif 'directory' in item:
                # サブディレクトリに対して再帰的に呼び出す
                add_recursive_files(item['directory'])
    except Exception as e:
        print(f"Error adding recursive files from {folder_path}: {e}")

def play_all_in_current_folder(folder_path):
    """現在のフォルダ以下のすべてのファイルを再生"""
    global is_playing
    try:
        client.clear()
        
        # 再帰的にすべてのファイルを追加
        add_recursive_files(folder_path)
        
        # キューに曲が追加されているか確認してから再生
        if int(client.status().get('playlistlength', 0)) > 0:
            client.play(0)
            is_playing = True
            print(f"Playing all files from: {folder_path}")
        else:
            print("No files found to play.")
            is_playing = False
            
    except Exception as e:
        print(f"Error playing all in folder: {e}")

def stop_playback():
    """再生停止"""
    global is_playing
    try:
        client.stop()
        is_playing = False
        print("Playback stopped")
    except Exception as e:
        print(f"Error stopping playback: {e}")

def get_playback_status():
    """再生状態を取得"""
    try:
        status = client.status()
        current = client.currentsong()
        
        state = status.get('state', 'stop')
        if current and 'title' in current:
            track = current['title']
        elif current and 'file' in current:
            track = current['file'].split('/')[-1]
        else:
            track = "Nothing playing"
        
        return state, track
    except Exception as e:
        print(f"Error getting status: {e}")
        return "stop", "Error"

def init_buttons():
    """ボタンイベントの初期化"""
    button1.when_pressed = handle_button
    button2.when_pressed = handle_button
    button3.when_pressed = handle_button
    button4.when_pressed = handle_button

def handle_button(bt):
    """ボタン入力の処理"""
    global selectedindex, files, pathes, operation_mode, previous_operation_mode, current_folder
 
# for button debug, uncomment some line and running script in terminal. 
#    print(f"Button pressed: {bt.pin}, current index: {selectedindex}, files count: {len(files)}")
    
    # 上ボタン (GPIO16)
    if str(bt.pin) == "GPIO16":
        if len(files) > 0:
            selectedindex -= 1
            if selectedindex < 0:
                selectedindex = 0
#            print(f"Up button: new index = {selectedindex}")
    
    # 下ボタン (GPIO 24/20)
    elif str(bt.pin) == "GPIO20":
        if len(files) > 0:
            selectedindex += 1
            if selectedindex >= len(files):
                selectedindex = len(files) - 1
#            print(f"Down button: new index = {selectedindex}")
    
    # 戻るボタン (GPIO6)
    elif str(bt.pin) == "GPIO6":
        if operation_mode == "browsing":
            # 親フォルダに戻る
            if current_folder:
                parent = '/'.join(current_folder.split('/')[:-1])
                current_folder = parent
                load_folder_contents(current_folder)
                selectedindex = 0
            else:
                # トップレベルならメインメニューに戻る
                operation_mode = "main screen"
                load_main_menu()
                selectedindex = 0
        elif operation_mode == "playing":
            stop_playback()
            operation_mode = "main screen"
            load_main_menu()
            selectedindex = 0
    
    # 決定ボタン (GPIO5)
    elif str(bt.pin) == "GPIO5":
        if operation_mode == "main screen":
            if files[selectedindex] == "BROWSE MUSIC":
                operation_mode = "browsing"
                current_folder = ""
                load_folder_contents(current_folder)
                selectedindex = 0
            elif files[selectedindex] == "PLAYBACK CONTROL":
                operation_mode = "playing"
        
        elif operation_mode == "browsing":
            if len(pathes) > 0:
                item_type, item_path, _ = pathes[selectedindex]
                
                if item_type == 'folder':
                    # フォルダを開く
                    current_folder = item_path
                    load_folder_contents(current_folder)
                    selectedindex = 0
                elif item_type == 'file':
                    # ファイルを再生
                    play_file(item_path)
                    operation_mode = "playing"
                elif item_type == 'special' and item_path == 'PLAY_ALL':
                    # 「すべて再生」を実行
                    play_all_in_current_folder(current_folder)
                    operation_mode = "playing"
    
    update_display()

def load_main_menu():
    """メインメニューをロード"""
    global pathes, files
    pathes = ["BROWSE MUSIC", "PLAYBACK CONTROL"]
    files = ["BROWSE MUSIC", "PLAYBACK CONTROL"]

def load_folder_contents(folder_path):
    """フォルダ内容をロード"""
    global pathes, files
    contents = get_folder_contents(folder_path)
    # 「すべて再生」オプションの定義
    # 形式: ('type', 'path/uri', 'display_name')
    # typeは'special'など、既存の'folder'/'file'と重複しないものにする
    play_all_option = ('special', 'PLAY_ALL', "[PLAY ALL RECURSIVE]")
    
    # 取得したコンテンツのリストに「すべて再生」オプションを追加
    contents.append(play_all_option)

    pathes = contents
    files = [item[2] for item in contents] # 表示名のみ

def update_display():
    """ディスプレイを更新"""
    draw.rectangle((0, 0, disp.width, disp.height), (0, 0, 0))
    
    if operation_mode == "playing":
        # 再生状態を表示
        state, track = get_playback_status()
        
        draw.text((10, 10), "NOW PLAYING:", font=font_small, fill=(100, 200, 255))
        
        # トラック名を折り返し表示
        y_offset = 40
        max_width = WIDTH - 20
        words = track.split()
        line = ""
        for word in words:
            test_line = line + word + " "
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                line = test_line
            else:
                draw.text((10, y_offset), line, font=font, fill=(255, 255, 255))
                y_offset += 30
                line = word + " "
        if line:
            draw.text((10, y_offset), line, font=font, fill=(255, 255, 255))
        
        # 状態表示
        state_text = "▶ PLAYING" if state == "play" else "⏸ PAUSED" if state == "pause" else "⏹ STOPPED"
        draw.text((10, HEIGHT - 40), state_text, font=font_small, fill=(255, 255, 0))
        draw.text((10, HEIGHT - 20), "Press BACK to stop", font=font_small, fill=(150, 150, 150))
    
    else:
        # メニュー/ブラウザ表示
        visible_items = 15
        start_index = max(0, selectedindex - visible_items + 1)
        
        for i in range(start_index, min(len(files), start_index + visible_items)):
            display_index = i - start_index
            y_pos = 10 + (display_index * 16)
            
            if i == selectedindex:
                draw.rectangle([5, y_pos, WIDTH - 5, y_pos + 15], fill=(255, 255, 255))
                text_color = (0, 0, 0)
            else:
                text_color = (255, 255, 255)
            
            # テキストを切り詰め
            text = files[i]
            if len(text) > 25:
                text = text[:22] + "..."
            
            draw.text((10, y_pos), text, font=font, fill=text_color)
    
    disp.display(img)

def status_update_loop():
    while True:
        try:
            # MPDサーバーの状態変化を待機 (通常、ここでスレッドがブロックされる)
            watch_client.idle() 
            # 状態が変わったら、すべての画面モードで表示を更新
            # (再生中の曲が進む場合も、通常MPDは'player'イベントを発生させる)
            update_display()
            time.sleep(1)
        except Exception as e:
            # 接続が切断された場合の対応
            print(f"MPD idle error: {e}. Reconnecting...")
            connect_mpd() # 再接続を試みる
            time.sleep(1)

# メイン処理
if __name__ == "__main__":
    # MPDに接続
    if not connect_mpd():
        print("Cannot connect to MPD. Exiting...")
        sys.exit(1)
    
    # ディスプレイ初期化
    if display_type in ("square", "rect", "round"):
        disp = st7789.ST7789(
            height=135 if display_type == "rect" else 240,
            rotation=0 if display_type == "rect" else 90,
            port=0,
            cs=st7789.BG_SPI_CS_FRONT,
            dc=9,
            backlight=13,
            spi_speed_hz=80 * 1000 * 1000,
            offset_left=0 if display_type == "square" else 40,
            offset_top=53 if display_type == "rect" else 0,
        )
    elif display_type == "dhmini":
        disp = st7789.ST7789(
            height=240,
            width=320,
            rotation=180,
            port=0,
            cs=1,
            dc=9,
            backlight=13,
            spi_speed_hz=60 * 1000 * 1000,
            offset_left=0,
            offset_top=0,
        )
    else:
        print("Invalid display type!")
        sys.exit(1)
    
    disp.begin()
    WIDTH = disp.width
    HEIGHT = disp.height
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("/home/sato/pmpdp/misaki/misaki_gothic.ttf", 16)
    font_small = ImageFont.truetype("/home/sato/pmpdp/misaki/misaki_gothic.ttf", 16)
    
    # 初期メニュー表示
    load_main_menu()
    update_display()
    
    # ボタンスレッド開始
    gpio_thread = threading.Thread(target=init_buttons)
    gpio_thread.daemon = True
    gpio_thread.start()
    
    # 状態更新スレッド開始
    status_thread = threading.Thread(target=status_update_loop)
    status_thread.daemon = True
    status_thread.start()
   
    #キープアライブスレッド開始
    keep_alive_thread = threading.Thread(target=keep_alive_loop)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()

    # メインループ
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nShutting down...")
        client.close()
        client.disconnect()
        sys.exit(0)

