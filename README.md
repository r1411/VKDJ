# VK DJ Bot

This bot allows people to send their songs into group's messages for further playback. 

## Installation
1. Enable Long Poll API in group settings.
2. Activate "Incoming message" event in Long Poll events
3. Get group API token
4. Rename config.json.example to config.json and edit it:
    - vk_token: group API token
    - vk_v: vk API version (can leave untouched)
    - vk_group_id: group's numeric id
    - vk_admin_ids: numeric ids of bot admins
    - song_duration_limit_seconds: Song duration limit in seconds
    - clear_saved_songs: Clear all downloaded songs after start?
    - allow_anybody_to_manage: Allow non-admins to skip and remove songs
5. Install requirements:
```pip install -r ./requirements.txt```

## Running

```sh
python3 ./main.py
```
Or
```sh
py -3 ./main.py
```

## Usage

Send songs that you would like to add to the group's messages. They will be queued automatically.

Available commands:
- /queue, /list - Show current song and queued songs
- /rem [idx], /remove [idx] - Remove song in queue by index
- /skip - Skip current song
- /pause - Pause / resume current song
- /song - Show latest song
- /help - Show these commands

## License

MIT
