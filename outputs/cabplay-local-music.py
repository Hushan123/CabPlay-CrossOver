#!/usr/bin/env python3
"""Add a reversible local music player to CabPlay 1.20.2 in CrossOver."""
import os
import socket
import time
import plistlib
import argparse
from colorsys import hls_to_rgb, rgb_to_hls
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

DOCS = Path.home() / "Documents/Euro Truck Simulator 2"
ASAR = Path.home() / ("Library/Application Support/CrossOver/Bottles/Steam/drive_c/users/"
                      "crossover/AppData/Local/Programs/CabPlay/resources/app.asar")
EXTS = {".mp3", ".flac", ".m4a", ".ogg", ".wav"}
MARKER = "ui/local-music.js"

PLAYER = r"""
(() => {
  const audio = new Audio();
  const game = new URLSearchParams(location.search).get('role') !== 'editor';
  const tracks = window.localLibrary.read();
  const playlistKey = 'cabplay-user-playlists-v1';
  let playlists = [];
  try { playlists = JSON.parse(localStorage.getItem(playlistKey)) || []; } catch {}
  let browsing = null, playingList = null, draft = null;
  function members(list) {
    if (!list) return tracks.map((_, i) => i);
    const positions = new Map(tracks.map((t,i) => [t.file,i]));
    return list.files.map(f => positions.get(f)).filter(i => i !== undefined);
  }
  const icons = {
    play: '<path fill="currentColor" d="M7 3.8v16.4L21 12 7 3.8Z"/>',
    pause: '<path fill="currentColor" d="M6 4h4v16H6zm8 0h4v16h-4z"/>',
    prev: '<path fill="currentColor" d="M4 5h2v14H4zm16 0v14L8 12z"/>',
    next: '<path fill="currentColor" d="M18 5h2v14h-2zM4 5l12 7-12 7z"/>',
    note: '<path d="M9 17V6l11-2v11M9 8l11-2M9 17c0 1.5-1.5 2.5-3 2.5S3 19 3 17.5 4.5 15 6 15s3 .5 3 2zm11-2c0 1.5-1.5 2.5-3 2.5s-3-.5-3-2 1.5-2.5 3-2.5 3 .5 3 2z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    up: '<path d="m6 15 6-6 6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    down: '<path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
  };
  let index = -1, view, page = 'now', error = '';
  let ownsMedia = false, pendingPlay = false, playRequest = 0;
  let queue = [], cursor = -1;
  const preferenceKey = 'cabplay-local-music-controls';
  let saved;
  try { saved = JSON.parse(localStorage.getItem(preferenceKey)); } catch { saved = null; }
  let mode = saved?.mode === 'shuffle' ? 'shuffle' : 'order';
  let volume = Number.isInteger(saved?.volume) && saved.volume >= 0 && saved.volume <= 100 ? saved.volume : 100;
  audio.volume = volume / 100;

  function saveControls() {
    try { localStorage.setItem(preferenceKey, JSON.stringify({ mode, volume })); } catch { /* playback still works */ }
  }
  function updateControls() {
    if (!view?.root.isConnected) return;
    view.volume.value = volume;
    view.volumeValue.textContent = volume + '%';
    view.order.setAttribute('aria-pressed', String(mode === 'order'));
    view.shuffle.setAttribute('aria-pressed', String(mode === 'shuffle'));
  }
  function setVolume(next) {
    volume = Math.max(0, Math.min(100, Number(next)));
    audio.volume = volume / 100;
    updateControls();
    saveControls();
  }
  function shuffled(indices) {
    for (let i = indices.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [indices[i], indices[j]] = [indices[j], indices[i]];
    }
    return indices;
  }
  function resetQueue() {
    queue = shuffled(members(playingList).filter(i => i !== index));
    cursor = -1;
    if (members(playingList).includes(index)) {
      queue.unshift(index);
      cursor = 0;
    }
  }
  function setMode(next) {
    if (mode === next) return;
    mode = next;
    if (mode === 'shuffle') resetQueue();
    updateControls();
    saveControls();
  }
  function step(direction) {
    const pool = members(playingList);
    if (!game || !pool.length) return;
    if (mode === 'order' || pool.length === 1) {
      const at = pool.indexOf(index);
      const next = at < 0 ? (direction < 0 ? pool.length - 1 : 0) : (at + direction + pool.length) % pool.length;
      if (pool[next] === index) audio.currentTime = 0;
      return select(pool[next]);
    }
    if (!queue.length) resetQueue();
    if (cursor + direction < 0) {
      const round = shuffled(pool.slice());
      if (round[round.length - 1] === queue[0]) round.reverse();
      queue.unshift(...round);
      cursor += round.length;
    }
    if (cursor + direction >= queue.length) {
      const round = shuffled(pool.slice());
      if (round[0] === index) [round[0], round[1]] = [round[1], round[0]];
      queue.push(...round);
    }
    cursor += direction;
    select(queue[cursor]);
  }
  function current() {
    const track = ownsMedia && tracks[index];
    if (!track) return null;
    return {
      track, playing: !audio.paused && !audio.ended, elapsed: audio.currentTime || 0,
      duration: Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : track.duration
    };
  }
  function notifyMedia() {
    window.dispatchEvent(new Event('cabplay-local-media'));
  }

  function icon(name) {
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + icons[name] + '</svg>';
  }
  function time(seconds) {
    const s = Math.floor(Number.isFinite(seconds) ? Math.max(0, seconds) : 0);
    return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
  }
  function setPage(next) {
    page = next;
    view.layout.dataset.page = page;
    const library = page === 'library';
    view.now.hidden = library;
    view.library.hidden = !library;
    view.nowTab.setAttribute('aria-pressed', String(!library));
    view.libraryTab.setAttribute('aria-pressed', String(library));
    if (!library) updateTime();
  }
  function updateTime() {
    if (page !== 'now' || !view?.root.isConnected || !view.root.classList.contains('active')) return;
    const elapsed = audio.currentTime || 0;
    const duration = Number.isFinite(audio.duration) && audio.duration > 0
      ? audio.duration : tracks[index >= 0 ? index : 0]?.duration || 0;
    const ratio = duration > 0 ? elapsed / duration : 0;
    view.elapsed.textContent = time(elapsed);
    view.remaining.textContent = '−' + time(duration - elapsed);
    view.seek.value = Math.round(ratio * 1000);
    view.seek.style.setProperty('--lm-progress', (ratio * 100) + '%');
    view.seek.disabled = !game || index < 0 || !Number.isFinite(audio.duration) || audio.duration <= 0;
  }
  function setArtwork(img, fallback, song) {
    img.hidden = !song?.cover;
    fallback.hidden = !!song?.cover;
    if (song?.cover) {
      const src = (song.cached ? 'cabmusic://art/' : 'local-music-art/') + song.cover;
      if (img.getAttribute('src') !== src) img.src = src;
    } else {
      img.removeAttribute('src');
    }
  }
  function setTheme(palette) {
    if (view.palette === palette) return;
    view.palette = palette;
    for (const name of ['glow', 'wash', 'base', 'accent', 'soft']) {
      if (palette?.[name]) view.layout.style.setProperty('--lm-' + name, palette[name]);
      else view.layout.style.removeProperty('--lm-' + name);
    }
  }
  function update() {
    if (!view?.root.isConnected) return;
    const song = tracks[index >= 0 ? index : 0];
    setTheme(song?.palette);
    view.title.textContent = song?.title || '资料库中没有歌曲';
    view.artist.textContent = song?.artist || '';
    view.album.textContent = song?.album || '';
    view.status.textContent = game ? error : '请在驾驶室的 CabPlay 屏幕上播放。';
    const playState = audio.paused ? ['play', '播放'] : ['pause', '暂停'];
    const [symbol, title] = playState;
    if (view.play.title !== title) {
      view.play.innerHTML = icon(symbol);
      view.play.title = title;
      view.play.setAttribute('aria-label', title);
    }
    setArtwork(view.cover, view.placeholder, song);
    view.rows.forEach((row, i) => row.setAttribute('aria-pressed', String(draft ? draft.files.includes(tracks[Number(row.dataset.track)].file) : index === Number(row.dataset.track))));
    updateTime();
  }
  function failed() {
    error = '这首歌无法播放，可以选择下一首。';
    update();
  }
  async function play() {
    const request = ++playRequest;
    pendingPlay = true;
    try {
      const state = await window.carplay?.radioState?.();
      if (state?.playing || state?.loading) await window.carplay.radioStop();
    } catch {
      // Local music can play without the radio bridge.
    }
    if (request !== playRequest) return;
    pendingPlay = false;
    ownsMedia = true;
    try {
      await audio.play();
    } catch (err) {
      if (request === playRequest && err.name !== 'AbortError') failed();
    }
  }
  function select(i) {
    if (!game || !tracks.length) return;
    const next = (i + tracks.length) % tracks.length;
    if (index !== next) {
      index = next;
      audio.src = 'cabmusic://tracks/' + encodeURIComponent(tracks[next].file);
    }
    error = '';
    play();
    update();
  }
  function toggle() {
    if (index < 0) return step(1);
    if (audio.paused && !pendingPlay) return play();
    pendingPlay = false;
    playRequest++;
    audio.pause();
  }
  function button(label, action, symbol) {
    const node = document.createElement('button');
    node.type = 'button';
    node.dataset.focus = '';
    if (symbol) {
      node.innerHTML = icon(symbol);
      node.title = label;
      node.setAttribute('aria-label', label);
    } else {
      node.textContent = label;
    }
    node.addEventListener('click', action);
    return node;
  }
  function addTracks() {
    view.list.replaceChildren();
    view.bar.replaceChildren();
    const refresh = () => { addTracks(); update(); };
    const persist = () => localStorage.setItem(playlistKey, JSON.stringify(playlists));
    const choose = list => { browsing = list; draft = null; refresh(); };
    if (draft) {
      const name = document.createElement('input');
      name.value = draft.name;
      name.placeholder = '播放列表名称';
      name.oninput = () => { draft.name = name.value; };
      view.bar.append(name, button('保存', () => {
        draft.name = draft.name.trim() || '我的播放列表';
        const list = browsing || {};
        Object.assign(list, draft);
        if (!browsing) playlists.push(list);
        if (playingList === list) { playingList = list.files.length ? list : null; queue = []; }
        persist(); choose(list);
      }), button('取消', () => choose(browsing)));
    } else {
      const picker = button(browsing ? browsing.name + ' ▾' : '全部歌曲 ▾', () => {
        view.list.replaceChildren();
        view.rows = [];
        for (const list of [null, ...playlists]) {
          const row = button(list ? list.name : '全部歌曲', () => choose(list));
          row.className = 'lm-collection';
          const art = document.createElement('span');
          art.className = 'lm-mosaic';
          const songs = members(list).map(i => tracks[i]).filter(t => t.cover);
          for (const song of songs.slice(0,4)) {
            const img = document.createElement('img');
            img.alt = '';
            img.src = (song.cached ? 'cabmusic://art/' : 'local-music-art/') + song.cover;
            art.append(img);
          }
          if (!art.childElementCount) art.innerHTML = icon('note');
          row.prepend(art);
          view.list.append(row);
        }
      });
      const edit = () => {
        draft = browsing ? {name:browsing.name, files:browsing.files.slice()} : {name:'播放列表 ' + (playlists.length+1),files:[]};
        refresh();
      };
      view.bar.append(picker, button('＋ 新建', () => { browsing = null; edit(); }));
      if (browsing) view.bar.append(button('编辑', edit), button('播放', () => {
        const pool = members(browsing);
        if (!pool.length) return;
        playingList = browsing;
        select(mode === 'shuffle' ? shuffled(pool)[0] : pool[0]); resetQueue(); setPage('now');
      }));
    }
    const indices = members(draft ? null : browsing);
    view.count.textContent = draft ? '勾选歌曲' : indices.length + ' 首歌曲';
    view.rows = indices.map(i => {
      const song = tracks[i];
      const row = button('', () => {
        if (draft) {
          if (draft.files.includes(song.file)) draft.files = draft.files.filter(f => f !== song.file);
          else draft.files.push(song.file);
          update(); return;
        }
        playingList = browsing;
        select(i);
        if (mode === 'shuffle') resetQueue();
        setPage('now');
        view.nowTab.focus({ preventScroll: true });
      });
      row.dataset.track = i;
      row.className = 'lm-track';
      row.disabled = !game;
      const art = document.createElement('span');
      art.className = 'lm-thumb';
      const image = document.createElement('img');
      image.alt = '';
      image.loading = 'lazy';
      const fallback = document.createElement('span');
      fallback.innerHTML = icon('note');
      setArtwork(image, fallback, song);
      art.append(image, fallback);
      const text = document.createElement('span');
      text.className = 'lm-track-text';
      const title = document.createElement('b');
      const artist = document.createElement('small');
      title.textContent = song.title;
      artist.textContent = [song.artist, song.album].filter(Boolean).join(' · ');
      text.append(title, artist);
      const duration = document.createElement('span');
      duration.className = 'lm-track-time';
      duration.textContent = song.duration > 0 ? time(song.duration) : '';
      row.append(art, text, duration);
      view.list.append(row);
      return row;
    });
  }
  // Refresh newly extracted artwork and tags without interrupting the current track.
  const pendingTags = tracks.some(t => t.pending);
  if (pendingTags) {
    const timer = setInterval(() => {
      const updated = new Map(window.localLibrary.read().map(t => [t.file,t]));
      let changed = false;
      for (const song of tracks) {
        const fresh = updated.get(song.file);
        if (song.pending && fresh && !fresh.pending) { Object.assign(song, fresh); changed = true; }
      }
      if (changed && view && !draft) { addTracks(); update(); }
      if (!tracks.some(t => t.pending && updated.has(t.file))) clearInterval(timer);
    }, 5000);
  }
  window.CabPlayLocalMusic = {
    mount(root) {
      if (!root || root === view?.root) return;
      root.innerHTML = '<div class="lm-layout"><div class="lm-tabs" role="group" aria-label="音乐页面"></div>' +
        '<div class="lm-now"><div class="lm-record"><div class="lm-art">' +
        '<img alt="" hidden><span aria-hidden="true">' + icon('note') + '</span></div></div>' +
        '<div class="lm-details"><strong class="lm-title"></strong><div class="lm-artist"></div>' +
        '<div class="lm-album"></div><div class="lm-timeline">' +
        '<input type="range" min="0" max="1000" value="0" aria-label="播放进度">' +
        '<div class="lm-times"><span>0:00</span><span>−0:00</span></div></div>' +
        '<div class="lm-controls"></div><div class="lm-options">' +
        '<div class="lm-modes" role="group" aria-label="播放顺序"></div>' +
        '<div class="lm-volume" role="group" aria-label="本地音乐音量"><span class="lm-volume-label">音量</span>' +
        '<input type="range" min="0" max="100" aria-label="本地音乐音量">' +
        '<output class="lm-volume-value"></output></div></div>' +
        '<div class="lm-status" role="status"></div></div></div>' +
        '<div class="lm-library" hidden><div class="lm-library-head"><strong>资料库</strong>' +
        '<span></span><div class="lm-scroll"></div></div><div class="lm-bar"></div><div class="lm-list"></div></div></div>';
      const q = selector => root.querySelector(selector);
      const nowTab = button('正在播放', () => setPage('now'));
      const libraryTab = button('资料库', () => setPage('library'));
      q('.lm-tabs').append(nowTab, libraryTab);
      const prev = button('上一首', () => step(-1), 'prev');
      const playButton = button('播放', toggle, 'play');
      const next = button('下一首', () => step(1), 'next');
      playButton.className = 'lm-play';
      q('.lm-controls').append(prev, playButton, next);
      [prev, playButton, next].forEach(node => { node.disabled = !game || !tracks.length; });
      const list = q('.lm-list');
      q('.lm-scroll').append(
        button('向上翻页', () => list.scrollBy(0, -list.clientHeight * 0.85), 'up'),
        button('向下翻页', () => list.scrollBy(0, list.clientHeight * 0.85), 'down'));
      const order = button('顺序', () => setMode('order'));
      const shuffle = button('随机', () => setMode('shuffle'));
      q('.lm-modes').append(order, shuffle);
      const volumeSlider = q('.lm-volume input');
      volumeSlider.addEventListener('input', () => setVolume(volumeSlider.value));
      const quieter = button('−', () => setVolume(volume - 5));
      const louder = button('+', () => setVolume(volume + 5));
      quieter.setAttribute('aria-label', '降低本地音乐音量');
      louder.setAttribute('aria-label', '提高本地音乐音量');
      q('.lm-volume').append(quieter, louder);
      const seek = q('.lm-timeline input');
      seek.disabled = true;
      seek.addEventListener('input', () => {
        if (index >= 0 && Number.isFinite(audio.duration)) audio.currentTime = seek.value / 1000 * audio.duration;
      });
      view = {
        root, bar: q('.lm-bar'), layout: q('.lm-layout'), nowTab, libraryTab, list, seek, play: playButton, count: q('.lm-library-head > span'),
        order, shuffle, volume: volumeSlider, volumeValue: q('.lm-volume-value'),
        now: q('.lm-now'), library: q('.lm-library'), cover: q('.lm-art img'), placeholder: q('.lm-art span'),
        title: q('.lm-title'), artist: q('.lm-artist'), album: q('.lm-album'), status: q('.lm-status'),
        elapsed: q('.lm-times span:first-child'), remaining: q('.lm-times span:last-child')
      };
      addTracks();
      setPage(page);
      updateControls();
      update();
    },
    current,
    openNow() {
      if (view?.root.isConnected) setPage('now');
      else page = 'now';
    },
    command(command) {
      if (command === 'next') step(1);
      if (command === 'previous') step(-1);
      if (command === 'toggle') toggle();
    },
    stopForRadio(state) {
      if (!state?.playing || !ownsMedia || pendingPlay) return;
      ownsMedia = false;
      audio.pause();
      notifyMedia();
    }
  };
  audio.addEventListener('ended', () => step(1));
  audio.addEventListener('error', failed);
  for (const event of ['play', 'pause', 'loadedmetadata', 'durationchange']) audio.addEventListener(event, () => {
    update();
    if (ownsMedia) notifyMedia();
  });
  audio.addEventListener('timeupdate', updateTime);
})();
"""

STYLES = r"""
.lm-layout {
  --lm-ink: #fbf7fa; --lm-muted: #d4c7d0; --lm-accent: #ffa0bc; --lm-soft: #ffc9da;
  --lm-glow: #74405c; --lm-wash: #442637; --lm-base: #19111c;
  width: 100%; height: 100%; padding: 2% 3.6% 2.6%; box-sizing: border-box;
  display: grid; grid-template-rows: auto minmax(0, 1fr); gap: 2.2%;
  overflow: hidden; color: var(--lm-ink); border: 1px solid #ffffff24; border-radius: 1.15em;
  background: #1a141b;
  font-size: clamp(13px, 2.45vmin, 24px);
}
.lm-layout[data-page="now"] {
  background: radial-gradient(ellipse 77% 112% at 12% 72%, var(--lm-glow) 0%, transparent 77%),
    linear-gradient(113deg, var(--lm-wash), var(--lm-base) 72%);
}
.lm-layout [hidden] { display: none !important; }
.lm-layout button {
  color: inherit; border: 0; padding: 0; font: inherit; background: transparent; cursor: pointer;
  display: grid; place-items: center; gap: 0.4em;
}
.lm-layout button:disabled { opacity: 0.38; cursor: default; }
.lm-layout button:focus-visible, .lm-layout input:focus-visible {
  outline: 0.12em solid var(--lm-accent); outline-offset: -0.12em;
}
.lm-layout svg { width: 1.4em; height: 1.4em; }
.lm-tabs { display: flex; width: max-content; align-items: center; gap: 0.55em; min-height: 2.65em; }
.lm-layout .lm-tabs button {
  min-height: 2.35em; padding: 0 0.75em; font-weight: 650; border-radius: 0.55em;
  color: var(--lm-muted); box-shadow: inset 0 -0.13em transparent;
}
.lm-layout .lm-tabs button[aria-pressed="true"] {
  color: var(--lm-ink); background: #ffffff19; box-shadow: inset 0 -0.13em var(--lm-accent);
}
.lm-now { display: grid; grid-template-columns: minmax(0, 45%) minmax(0, 1fr); gap: 6%; align-items: center; min-height: 0; }
.lm-record { min-width: 0; min-height: 0; height: 100%; display: grid; place-items: center; }
.lm-art {
  width: min(100%, 59vh); aspect-ratio: 1; display: grid; place-items: center; overflow: hidden;
  color: var(--lm-soft); background: var(--lm-wash); border-radius: 0.7em;
  box-shadow: 0 0.95em 2.65em #08040ba8, 0 0 0 1px #ffffff33;
}
.lm-art img { width: 100%; height: 100%; object-fit: contain; }
.lm-art svg { width: 3.4em; height: 3.4em; }
.lm-details { min-width: 0; padding-right: 1%; }
.lm-title, .lm-artist, .lm-album, .lm-track-text > * {
  display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.lm-title { font-size: clamp(20px, 4.85vmin, 48px); line-height: 1.18; letter-spacing: -0.025em; }
.lm-artist { color: var(--lm-soft); font-weight: 550; margin-top: 0.28em; }
.lm-album { color: var(--lm-muted); font-size: 0.85em; margin-top: 0.14em; }
.lm-artist:empty, .lm-album:empty, .lm-status:empty { display: none; }
.lm-timeline { margin-top: 1.04em; }
.lm-layout .lm-timeline input[type="range"] {
  width: 100%; height: 1.16em; margin: 0; appearance: none; cursor: pointer; background: transparent;
}
.lm-layout .lm-timeline input[type="range"]::-webkit-slider-runnable-track {
  height: 0.18em; border-radius: 1em;
  background: linear-gradient(to right, var(--lm-accent) var(--lm-progress, 0%), #ffffff45 var(--lm-progress, 0%));
}
.lm-layout .lm-timeline input[type="range"]::-webkit-slider-thumb {
  appearance: none; width: 0.65em; height: 0.65em; margin-top: -0.24em; background: var(--lm-soft); border-radius: 50%;
}
.lm-layout .lm-timeline input[type="range"]:disabled { cursor: default; }
.lm-times { display: flex; justify-content: space-between; color: var(--lm-muted); font-size: 0.76em; font-variant-numeric: tabular-nums; }
.lm-controls { display: flex; gap: 0.75em; align-items: center; margin-top: 1.05em; }
.lm-layout .lm-controls button { width: 2.7em; height: 2.7em; border-radius: 0.8em; background: #ffffff18; }
.lm-layout .lm-controls .lm-play {
  width: 3.45em; height: 3.15em; border-radius: 1.05em 1.05em 1.05em 0.45em;
  background: var(--lm-accent); color: #1a1018;
}
.lm-controls .lm-play svg { width: 1.6em; height: 1.6em; }
.lm-options { display: flex; flex-wrap: wrap; gap: 0.42em 0.9em; align-items: center; margin-top: 0.7em; }
.lm-modes, .lm-volume { display: flex; gap: 0.25em; align-items: center; font-size: 0.75em; }
.lm-layout .lm-options button { min-height: 2.2em; min-width: 2.2em; padding: 0 0.48em; border-radius: 0.5em; background: #ffffff17; white-space: nowrap; }
.lm-layout .lm-modes button[aria-pressed="true"] { background: var(--lm-accent); color: #1a1018; }
.lm-layout .lm-volume input { appearance: auto; accent-color: var(--lm-accent); width: clamp(38px, 7.6vw, 102px); }
.lm-volume-value { margin-right: 0.2em; min-width: 3em; font-variant-numeric: tabular-nums; text-align: right; }
.lm-status { font-size: 0.78em; color: var(--lm-soft); margin-top: 0.65em; }
.lm-library { min-height: 0; display: flex; flex-direction: column; }
.lm-library-head { display: flex; align-items: center; gap: 0.6em; margin-bottom: 0.35em; }
.lm-library-head strong { font-size: 1.28em; }
.lm-library-head > span, .lm-track small, .lm-track-time { color: var(--lm-muted); font-size: 0.8em; }
.lm-scroll { margin-left: auto; display: flex; gap: 0.48em; }
.lm-layout .lm-scroll button { min-width: 2.25em; height: 2em; border-radius: 0.5em; background: #ffffff19; }
.lm-list { flex: 1; min-height: 0; overflow: auto; overscroll-behavior: contain; scrollbar-width: thin; }
.lm-layout .lm-track {
  width: 100%; display: grid; grid-template-columns: 2.1em minmax(0, 1fr) 3.1em; gap: 0.75em;
  justify-items: start; text-align: left; align-items: center; border-bottom: 1px solid #ffffff1c;
  min-height: 2.8em; padding: 0.34em 0.7em; border-radius: 0.4em;
}
.lm-layout .lm-track[aria-pressed="true"] { background: #ffffff1e; box-shadow: inset 0.15em 0 var(--lm-accent); }
.lm-thumb { width: 2em; aspect-ratio: 1; display: grid; place-items: center; overflow: hidden; background: #60354b; border-radius: 0.38em; }
.lm-thumb img { width: 100%; height: 100%; object-fit: cover; }
.lm-thumb svg { width: 1.15em; height: 1.15em; color: #ffc2cf; }
.lm-track-text { display: block; width: 100%; min-width: 0; }
.lm-track-time { justify-self: end; font-variant-numeric: tabular-nums; }
.lm-library-head strong { font-size:1.7em; letter-spacing:-.045em; }
.lm-bar { display:flex; align-items:center; gap:.45em; flex-wrap:wrap; margin-bottom:.5em; }
.lm-layout .lm-bar button,.lm-layout .lm-collection { color:#ff93a8; background:#502b39; border-radius:.65em; padding:.35em .75em; }
.lm-bar input { min-width:0; width:42%; font:inherit; border:0; border-radius:.45em; padding:.35em; }
.lm-collection { display:block; width:100%; text-align:left; margin-bottom:.35em; }
.lm-layout .lm-collection { display:flex; gap:.85em; align-items:center; padding:.38em .7em; background:#ffffff09; color:#fff; font-weight:650; }
.lm-mosaic { display:grid; grid-template:1fr 1fr / 1fr 1fr; width:2.8em; height:2.8em; border-radius:.45em; overflow:hidden; background:linear-gradient(145deg,#f77588,#722542); }
.lm-mosaic img { width:100%; height:100%; object-fit:cover; min-height:0; }
.lm-mosaic img:only-child,.lm-mosaic svg { grid-area:1 / 1 / 3 / 3; align-self:center; justify-self:center; }
.lm-layout[data-page="library"] { background:linear-gradient(155deg,#39222e,#18151d 55%); }
.lm-title { letter-spacing:-.035em; }
.lm-art { box-shadow:0 .7em 1.8em #0006; }
.lm-library:has(.lm-bar input) .lm-track[aria-pressed=true] .lm-track-time::before { content:'✓ '; color:#ff93a8; }
@media (max-height: 410px) {
  .lm-layout { padding-top: 1%; }
  .lm-art { width: min(100%, 49vh); }
  .lm-timeline, .lm-controls { margin-top: 0.6em; }
  .lm-layout .lm-controls .lm-play { width: 2.7em; height: 2.7em; }
  .lm-options { margin-top: 0.4em; }
}
"""

PROTOCOL = r"""
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { Readable } = require('node:stream');
const tracks = require('../ui/local-music-index.json');
const types = { '.mp3': 'audio/mpeg', '.flac': 'audio/flac', '.m4a': 'audio/mp4',
  '.ogg': 'audio/ogg', '.wav': 'audio/wav' };

function install(protocol, documents) {
  const root = path.join(documents, 'Euro Truck Simulator 2', 'music');
  const cache = path.join(root, '.cabplay');
  require('electron').ipcMain.on('localmusic:catalog', event => {
    let cached = {};
    try { cached = JSON.parse(fs.readFileSync(path.join(cache,'catalog.json'),'utf8')); } catch {}
    const bundled = new Map(tracks.map(t => [t.file,t]));
    try {
      event.returnValue = fs.readdirSync(root,{withFileTypes:true})
        .filter(e => e.isFile() && !e.name.startsWith('.') && types[path.extname(e.name).toLowerCase()])
        .sort((a,b) => a.name.localeCompare(b.name, 'zh-CN', {numeric:true}))
        .map(e => {
          const hit = Object.hasOwn(cached,e.name) && cached[e.name];
          const base = bundled.get(e.name) || {file:e.name,title:path.parse(e.name).name};
          const stat = fs.statSync(path.join(root,e.name));
          const valid = hit && hit.stamp[0] === stat.size && Math.abs(hit.stamp[1]/1e6 - stat.mtimeMs) < 2;
          return valid ? {...hit.song,cached:true,pending:false} : {...base,pending:true};
        });
    } catch { event.returnValue = []; }
  });
  protocol.handle('cabmusic', async request => {
    const url = new URL(request.url);
    if (!['GET', 'HEAD'].includes(request.method)) return new Response(null, { status: 405 });
    if (url.hostname === 'art' && /^\/[0-9a-f]{24}\.jpg$/.test(url.pathname)) {
      try { return new Response(await fs.promises.readFile(path.join(cache,url.pathname.slice(1))), {headers:{'Content-Type':'image/jpeg'}}); }
      catch { return new Response(null,{status:404}); }
    }
    if (url.hostname !== 'tracks' || url.search)
      return new Response(null, { status: 404 });
    const name = decodeURIComponent(url.pathname.slice(1));
    if (!name || name !== path.basename(name) || /[\\/:]/.test(name)) return new Response(null, { status: 404 });
    const type = types[path.extname(name).toLowerCase()];
    if (!type) return new Response(null, { status: 404 });

    let file, size;
    try {
      const realRoot = await fs.promises.realpath(root);
      file = await fs.promises.realpath(path.join(realRoot, name));
      const rel = path.relative(realRoot, file);
      if (!rel || path.isAbsolute(rel) || rel === '..' || rel.startsWith('..' + path.sep))
        return new Response(null, { status: 404 });
      const stat = await fs.promises.stat(file);
      if (!stat.isFile() || !stat.size) return new Response(null, { status: 404 });
      size = stat.size;
    } catch {
      return new Response(null, { status: 404 });
    }

    const headers = new Headers({ 'Content-Type': type, 'Accept-Ranges': 'bytes' });
    let start = 0, end = size - 1;
    const range = request.headers.get('range');
    if (range) {
      const match = /^bytes=(\d*)-(\d*)$/i.exec(range);
      if (match?.[1]) {
        start = Number(match[1]);
        if (match[2]) end = Math.min(end, Number(match[2]));
      } else if (match?.[2]) {
        start = Math.max(0, size - Number(match[2]));
      }
      if (!match || (!match[1] && !match[2]) || !Number.isSafeInteger(start) || start > end) {
        headers.set('Content-Range', 'bytes */' + size);
        return new Response(null, { status: 416, headers });
      }
      headers.set('Content-Range', 'bytes ' + start + '-' + end + '/' + size);
    }
    headers.set('Content-Length', String(end - start + 1));
    const body = request.method === 'HEAD' ? null : Readable.toWeb(fs.createReadStream(file, { start, end }));
    return new Response(body, { status: range ? 206 : 200, headers });
  });
}
module.exports = { install };
"""

ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/><path d="M13 7a5 5 0 0 1 4 4M7 13a5 5 0 0 0 4 4"/></svg>'


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def unpack(data):
    first, header, payload, length = struct.unpack_from("<IIII", data)
    end = 8 + header
    if first != 4 or payload != header - 4 or not 0 < length <= end-16 or end > len(data):
        raise ValueError("无法读取 CabPlay 文件头。")
    return json.loads(data[16:16+length]), data[end:]


def entry(tree, name, create=False):
    *folders, key = name.split("/")
    entries = tree["files"]
    for folder in folders:
        entries = (entries.setdefault(folder, {"files": {}}) if create else entries[folder])["files"]
    return entries, key


def get(tree, payload, name):
    entries, key = entry(tree, name)
    item = entries[key]
    start = int(item["offset"])
    return payload[start:start + item["size"]]


def is_patched(tree):
    entries, key = entry(tree, MARKER)
    return key in entries


def archive_with(original, changes):
    header, payload = unpack(original)
    out = bytearray(payload)
    for name, content in changes.items():
        entries, key = entry(header, name, create=True)
        block = 4 * 1024 * 1024
        entries[key] = {
            "offset": str(len(out)), "size": len(content),
            "integrity": {"algorithm": "SHA256", "hash": hashlib.sha256(content).hexdigest(),
                          "blockSize": block, "blocks": [
                              hashlib.sha256(content[i:i+block]).hexdigest()
                              for i in range(0, len(content), block)]},
        }
        out.extend(content)
    raw = encode(header)
    padding = bytes((-len(raw)) % 4)
    size = 4 + len(raw) + len(padding)
    return struct.pack("<IIII", 4, size+4, size, len(raw)) + raw + padding + out


def raw_m4a_cover(file):
    # Mp3tag can write a covr data type that FFprobe omits from attached_pic.
    raw = file.read_bytes()
    start = 0
    while (i := raw.find(b"covr", start)) != -1:
        start = i + 4
        if i < 4 or i+20 > len(raw) or raw[i+8:i+12] != b"data":
            continue
        parent = int.from_bytes(raw[i-4:i], "big")
        size = int.from_bytes(raw[i+4:i+8], "big")
        end = i+4+size
        if 16 <= size <= parent-8 and end <= len(raw):
            image = raw[i+20:end]
            if image.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")):
                return image
    return None


def thumbnail(ffmpeg, inputs, data=None):
    run = subprocess.run([
        ffmpeg, "-nostdin", "-v", "error", *inputs, "-frames:v", "1",
        "-vf", "scale=320:320:force_original_aspect_ratio=decrease",
        "-pix_fmt", "yuvj420p", "-threads", "1", "-c:v", "mjpeg", "-f", "image2pipe", "pipe:1",
    ], input=data, capture_output=True, timeout=20)
    img = run.stdout
    return img if run.returncode == 0 and img.startswith(b"\xff\xd8") and img.endswith(b"\xff\xd9") else None


def cover_palette(ffmpeg, image):
    pixels = subprocess.run([
        ffmpeg, "-nostdin", "-v", "error", "-f", "mjpeg", "-i", "pipe:0",
        "-frames:v", "1", "-vf", "scale=28:28:flags=area", "-pix_fmt", "rgb24",
        "-threads", "1", "-f", "rawvideo", "pipe:1",
    ], input=image, capture_output=True, timeout=15)
    raw = pixels.stdout
    if pixels.returncode or len(raw) != 28 * 28 * 3:
        return None

    buckets = [0.0] * 24
    total_lightness = 0.0
    for i in range(0, len(raw), 3):
        hue, lightness, saturation = rgb_to_hls(*(c / 255 for c in raw[i:i+3]))
        total_lightness += lightness
        if 0.12 < lightness < 0.90 and saturation > 0.18:
            buckets[round(hue * len(buckets)) % len(buckets)] += saturation * (1 - abs(lightness - 0.5))

    strength = [value + 0.45 * (buckets[i-1] + buckets[(i+1) % len(buckets)])
                for i, value in enumerate(buckets)]
    bucket = max(range(len(strength)), key=strength.__getitem__)
    hue = bucket / len(buckets)
    colourful = strength[bucket] > 7
    brightness = total_lightness / (len(raw) / 3)

    def tone(lightness, saturation):
        channels = hls_to_rgb(hue, lightness, saturation if colourful else 0)
        return "#" + "".join(f"{round(channel * 255):02x}" for channel in channels)

    return {
        "glow": tone(0.28 + brightness * 0.22, 0.56),
        "wash": tone(0.14 + brightness * 0.09, 0.42),
        "base": tone(0.065 + brightness * 0.055, 0.30),
        "accent": tone(0.75, 0.78),
        "soft": tone(0.88, 0.56),
    }


def scan(folder, only=None):
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("需要 ffmpeg 和 ffprobe。")
    files = sorted((p for p in folder.iterdir() if p.is_file() and not p.is_symlink()
                    and p.suffix.lower() in EXTS and not p.name.startswith(".")), key=lambda p: p.name.casefold())
    if only is not None:
        files = [p for p in files if p.name in only]

    def inspect(file):
        result = subprocess.run([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(file)],
                                capture_output=True, check=True, timeout=20)
        report = json.loads(result.stdout)
        streams = report.get("streams", [])
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        if not audio:
            raise ValueError(f"未找到音轨：{file.name}")
        fmt = report.get("format", {})
        tags = {k.lower(): v for k, v in {**audio.get("tags", {}), **fmt.get("tags", {})}.items()}
        picture = next((s for s in streams if s.get("disposition", {}).get("attached_pic")), None)
        image = thumbnail(ffmpeg, ["-i", str(file), "-map", f"0:{picture['index']}"]) if picture else None
        if image is None and file.suffix.lower() == ".m4a":
            cover = raw_m4a_cover(file)
            if cover:
                image = thumbnail(ffmpeg, ["-i", "pipe:0"], cover)
        length = fmt.get("duration") or audio.get("duration")
        return ({"file": file.name, "title": tags.get("title") or file.stem, "artist": tags.get("artist", ""),
                 "album": tags.get("album", ""), "duration": float(length) if length and length != "N/A" else 0},
                image)

    tracks, covers, palettes = [], {}, {}
    with ThreadPoolExecutor(max_workers=4) as workers:
        for song, image in workers.map(inspect, files):
            if image:
                name = hashlib.sha256(image).hexdigest()[:24] + ".jpg"
                key = "ui/local-music-art/" + name
                if key not in covers:
                    covers[key] = image
                    palettes[name] = cover_palette(ffmpeg, image)
                song["cover"] = name
                if palettes[name]:
                    song["palette"] = palettes[name]
            tracks.append(song)
    return tracks, covers


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError("CabPlay 的程序结构与补丁不匹配。")
    return text.replace(old, new, 1)


def ultra_texture_config(data, values=None):
    """Read or replace only the two INI switches used by this repair."""
    import re
    sections = re.split(rb"(?m)^(?=\[)", data)
    found = {}
    for i, section in enumerate(sections):
        for group, key in ((b"render", b"mipmaps"), (b"cluster", b"enabled")):
            if section.splitlines()[:1] != [b"[" + group + b"]"]:
                continue
            pattern = rb"(?m)^(" + key + rb"=)([01])(?=\r?$)"
            matches = list(re.finditer(pattern, section))
            if key in found or len(matches) != 1:
                raise ValueError("Ultra 配置项重复或缺失。")
            match = matches[0]
            found[key] = match[2]
            if values is not None:
                sections[i] = section[:match.start(2)] + values[key] + section[match.end(2):]
    if len(found) != 2:
        raise ValueError("无法找到 Ultra 或原生纹理设置。")
    return found, b"".join(sections)


def enable_ultra(archive, config, restore=False):
    backup = config.with_name("cabplay.ini.before-ultra-texture")
    ini = config.read_bytes()
    if restore:
        values, _ = ultra_texture_config(backup.read_bytes())
        _, result = ultra_texture_config(ini, values)
        atomic_write(config, result)
        print("已恢复原先的 Ultra 开关和纹理模式。")
        return
    _, updated = ultra_texture_config(ini, {b"mipmaps": b"1", b"enabled": b"1"})
    current = archive.read_bytes()
    tree, payload = unpack(current)
    if json.loads(get(tree, payload, "package.json"))["version"] != "1.20.2":
        raise ValueError("此补丁适用于当前安装的 CabPlay 1.20.2。")
    name = "main/cluster-window.js"
    module = get(tree, payload, name)
    new = current
    if b"cabplayWarmupTimer" in module or b"(settingsNow().clusterDesign === 'tesla')" in module:
        original = archive.with_name("app.asar.before-local-music").read_bytes()
        oh, od = unpack(original)
        if is_patched(oh) or json.loads(get(oh, od, "package.json"))["version"] != "1.20.2":
            raise ValueError("原版备份校验失败。")
        stock = get(oh, od, name)
        verify_executable(archive)
        new = archive_with(current, {name: stock})
        if get(*unpack(new), name) != stock:
            raise ValueError("原生仪表界面恢复校验失败。")
    if not backup.exists():
        with backup.open("xb") as f:
            f.write(ini)
    if current != archive.read_bytes() or ini != config.read_bytes():
        raise ValueError("CabPlay 配置已变化，退出后重试。")
    if new != current:
        atomic_write(archive, new)
    if updated != ini:
        atomic_write(config, updated)
    print("Ultra 已设为随游戏启动，已请求 GPU mipmap 纹理模式。")


def build(original, tracks, covers):
    header, data = unpack(original)

    def source(name):
        return get(header, data, name).decode()

    version = json.loads(source("package.json"))["version"]
    if version != "1.20.2" or is_patched(header):
        raise ValueError(f"此补丁仅适用于原版 CabPlay 1.20.2，检测到 {version}。")
    main = replace(source("main.js"), "corsEnabled: true } }]);",
                   "corsEnabled: true } }, { scheme: 'cabmusic', privileges: "
                   "{ standard: true, secure: true, stream: true } }]);")
    original_setup = "  setupDataProtocol({ protocol, net, dataDir, appDir: __dirname, mapData, sports, brandLogos });"
    main = replace(main, original_setup, original_setup +
                   "\n  require('./main/local-music').install(protocol, app.getPath('documents'));")
    defaults = replace(source("ui/defaults.js"), "    radio: { name: 'Radio', color: 'red', kind: 'audio' },",
                       "    localmusic: { name: '本地音乐', color: 'pink', kind: 'audio' },\n"
                       "    radio: { name: 'Radio', color: 'red', kind: 'audio' },")
    anchor = "      for (const id of appIds) if (!home.includes(id)) home.push(id);"
    defaults = replace(defaults, anchor,
                       "      if (!home.includes('localmusic')) home.splice(home.indexOf('music') + 1, 0, 'localmusic');\n"
                       + anchor)
    app = replace(source("ui/app.js"), "  const ICONS = window.CarPlayIcons;",
                  "  const ICONS = { ...window.CarPlayIcons, localmusic: " + json.dumps(ICON) + " };")
    anchor = '      <section class="screen" data-screen="dashboard">'
    app = replace(app, anchor, '      <section class="screen" data-screen="localmusic"></section>\n' + anchor)
    anchor = "    if (id === 'phone') renderPhone();"
    app = replace(app, anchor, anchor + "\n    if (id === 'localmusic') window.CabPlayLocalMusic.mount("
                  "stage.querySelector('[data-screen=\"localmusic\"]'));")
    app = replace(app, "    if (id === 'nowplaying') id = catalog.APPS[settings.recents?.audio] ? settings.recents.audio : 'music';",
                  """    if (id === 'nowplaying') {
      const local = window.CabPlayLocalMusic;
      const recent = catalog.APPS[settings.recents?.audio] ? settings.recents.audio : 'music';
      id = local.current() ? 'localmusic' : radio?.playing ? 'radio' : media?.playing ? 'music' : recent;
      if (id === 'localmusic') local.openNow();
    }""")
    app = replace(app, """      if (d.open === 'music' && d.musicNow) {""",
                  """      if (d.musicNow && window.CabPlayLocalMusic.current()) return showScreen('nowplaying');
      if (d.open === 'music' && d.musicNow) {""")
    app = replace(app, """    } else if (d.cmd) sendMedia(d.cmd);""",
                  """    } else if (d.cmd) {
      const local = window.CabPlayLocalMusic;
      if (el.closest('.w-music') && local.current()) local.command(d.cmd);
      else sendMedia(d.cmd);
    }""")
    widget = """
  function syncLocalMusicWidget(progressOnly = false) {
    const local = window.CabPlayLocalMusic.current();
    if (!local || (progressOnly && screen !== 'dashboard')) return;
    if (!progressOnly) shell.classList.remove('radio-src');
    const ratio = local.duration > 0 ? Math.min(1, local.elapsed / local.duration) : 0;
    for (const widget of stage.querySelectorAll('.w-music')) {
      const progress = widget.querySelector('[data-bind="progress"]');
      if (progress) progress.style.width = (Math.round(ratio * 400) / 4) + '%';
      if (progressOnly) continue;
      const { track, playing } = local;
      for (const key of ['title', 'artist']) {
        const text = widget.querySelector('.wm [data-bind="' + key + '"]');
        if (text && text.textContent !== (track[key] || '')) text.textContent = track[key] || '';
      }
      const art = widget.querySelector('.wm [data-bind="art"]');
      if (art) {
        const value = track.cover ? 'url("' + (track.cached ? 'cabmusic://art/' : 'local-music-art/') + encodeURIComponent(track.cover) + '")' : '';
        if (art.style.backgroundImage !== value) art.style.backgroundImage = value;
        art.classList.toggle('empty', !track.cover);
      }
      const play = widget.querySelector('.controls [data-bind="play"]');
      if (play && play.dataset.state !== String(playing)) {
        play.innerHTML = playing ? ICONS.pause : ICONS.play;
        play.dataset.state = String(playing);
      }
    }
  }
  window.addEventListener('cabplay-local-media', () => {
    if (window.CabPlayLocalMusic.current()) syncLocalMusicWidget();
    else onMedia(media || { available: false }, true);
  });
"""
    anchor = "  function onMedia(m, rebinding = false) {"
    app = replace(app, anchor, widget + anchor)
    anchor = "    if (musicTab === 'lyrics' && !rebinding) loadLyrics();"
    app = replace(app, anchor, "    syncLocalMusicWidget();\n" + anchor)
    anchor = "      width('progress', dur ? Math.round((pos / dur) * 400) / 400 : 0);"
    app = replace(app, anchor, anchor + "\n      syncLocalMusicWidget(true);")
    anchor = "  function onRadio(state) {\n    radio = state;"
    app = replace(app, anchor + "\n    renderRadio();", anchor +
                  "\n    window.CabPlayLocalMusic.stopForRadio(state);\n    renderRadio();\n    syncLocalMusicWidget();")
    html = replace(source("ui/index.html"), "media-src 'self' data: http: https:;",
                   "media-src 'self' data: http: https: cabmusic://tracks;")
    html = replace(html, "</head>", '  <link rel="stylesheet" href="local-music.css">\n</head>')
    html = replace(html, '  <script src="app.js"></script>',
                   '  <script src="local-music-index.js"></script>\n  <script src="local-music.js"></script>\n'
                   '  <script src="app.js"></script>')
    remote_html = replace(source("ui/remote.html"), "  </style>", """    body.display-only { flex-direction: column; }
    .display-only .bar { display: none; }
    .display-only .screen { padding: 0; grid-template: minmax(0, 1fr) / minmax(0, 1fr); }
    .display-only img { border-radius: 0; }
  </style>""")
    remote_html = replace(remote_html, "<body>", """<body class="display-only">
  <script>
    if (new URLSearchParams(location.search).get('toolbar') === '1') {
      document.body.classList.remove('display-only');
    }
  </script>""")
    remote_html = replace(remote_html, "aspect-ratio: 16 / 9; ", "")
    remote_html = replace(remote_html, "q('/frame.jpg') + '&after='",
                          "q('/frame.jpg') + (window.cabPlayWired ? '&wired=1' : '') + '&after='")
    remote_server = source("remote.js")
    remote_server = replace(remote_server, "  frame() {", """  frame(wired = false) {
    const key = wired ? 'wiredCache' : 'cache';
    const cache = this[key] || { id: 0 };
    const started = Date.now();""")
    remote_server = replace(remote_server, "if (image !== this.cache.image) {",
        "if (image !== cache.image && started - (cache.encodedAt ?? -Infinity) >= (wired ? 16 : 33)) {")
    remote_server = replace(remote_server, "      const started = Date.now();\n      const small = width > 1280 ? image.resize({ width: 1280, quality: 'good' }) : image;",
        "      const limit = wired ? 2560 : 1920;\n"
        "      const small = width > limit ? image.resize({ width: limit, quality: 'good' }) : image;")
    remote_server = replace(remote_server, "this.cache = { image, jpeg: small.toJPEG(70), id: this.cache.id + 1 };",
        "this[key] = { image, jpeg: small.toJPEG(wired ? 96 : 90), id: cache.id + 1, encodedAt: started };")
    remote_server = replace(remote_server, "return this.cache;", "return this[key];")
    remote_server = replace(remote_server, "const f = this.frame();", "const f = this.frame(url.searchParams.get('wired') === '1');")
    remote_server = replace(remote_server, "setTimeout(reply, 20);", "setTimeout(reply, 4);")
    remote_server = replace(remote_server, "const after = Number(url.searchParams.get('after'))",
        "if (url.searchParams.get('wired') === '1') this.lastWired = Date.now();\n      const after = Number(url.searchParams.get('after'))")
    main = replace(main, "  if (!gpuMode || !remote.active || !remoteDirty", """  if (!gameWin || gameWin.isDestroyed()) return;
  const remoteFps = Date.now() - (remote.lastWired || 0) < 3000 ? 60 : 30;
  const wantedFps = remote.active ? Math.max(remoteFps, screen.fps) : screen.fps;
  if (gameWin.webContents.getFrameRate() !== wantedFps) gameWin.webContents.setFrameRate(wantedFps);
  if (!gpuMode || !remote.active || !remoteDirty""")
    main = replace(main, "}, 66);", "}, 16);")
    html = replace(html, "img-src 'self' data:", "img-src 'self' cabmusic: data:")
    preload = source("preload.js") + """
require('electron').contextBridge.exposeInMainWorld('localLibrary', {
  read: () => require('electron').ipcRenderer.sendSync('localmusic:catalog')
});
"""
    renderer_tracks = [{key: value for key, value in track.items() if key != "file"} for track in tracks]
    result = archive_with(original, {
        **covers, "preload.js": preload.encode(), "main.js": main.encode(), "ui/defaults.js": defaults.encode(), "ui/app.js": app.encode(),
        "ui/index.html": html.encode(), "main/local-music.js": PROTOCOL.encode(), MARKER: PLAYER.encode(),
        "ui/remote.html": remote_html.encode(),
        "remote.js": remote_server.encode(),
        "ui/local-music.css": STYLES.encode(), "ui/local-music-index.json": encode(tracks),
        "ui/local-music-index.js": b"window.CabPlayLocalTracks = " + encode(renderer_tracks) + b";\n",
    })
    h, data = unpack(result)
    if not is_patched(h) or json.loads(get(h, data, "ui/local-music-index.json")) != tracks:
        raise ValueError("补丁校验失败。")
    return result


def verify_executable(archive):
    # Electron fuse wire, v1: index 4 is EnableEmbeddedAsarIntegrityValidation.
    marker = b"dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX"
    exe = (archive.parent.parent / "CabPlay.exe").read_bytes()
    i = exe.find(marker)
    wire = exe[i+len(marker):i+len(marker)+10] if i >= 0 else b""
    if len(wire) != 10 or wire[:2] != b"\x01\x08" or wire[6:7] != b"0":
        raise ValueError("CabPlay 的 ASAR 校验配置不匹配。")


def atomic_write(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".cabplay-", delete=False) as temp:
        staged = Path(temp.name)
        try:
            temp.write(data)
            temp.flush()
            temp.close()
            staged.chmod((path.stat().st_mode & 0o777) if path.exists() else 0o600)
            staged.replace(path)
        finally:
            staged.unlink(missing_ok=True)


USB_LABEL = "local.cabplay.usb-display"
USB_PORT = 48723
USB_SUPPORT = Path.home() / "Library/Application Support/CabPlayPad"
USB_AGENT = Path.home() / "Library/LaunchAgents" / (USB_LABEL + ".plist")


def exact(sock, size):
    data = bytearray()
    while len(data) < size:
        block = sock.recv(size - len(data))
        if not block:
            raise EOFError
        data.extend(block)
    return bytes(data)


def mux_request(sock, message):
    body = plistlib.dumps(dict(message, ClientVersionString="CabPlayPad/1.2", ProgName="CabPlayPad", kLibUSBMuxVersion=3))
    sock.sendall(struct.pack("<4I", 16 + len(body), 1, 8, 1) + body)
    size, version, kind, tag = struct.unpack("<4I", exact(sock, 16))
    if (version, kind, tag) != (1, 8, 1) or not 16 < size <= 4194304:
        raise ValueError("无效 USB 响应")
    return plistlib.loads(exact(sock, size - 16))


def usb_socket():
    sock = socket.socket(socket.AF_UNIX)
    try:
        sock.settimeout(4)
        sock.connect("/var/run/usbmuxd")
    except OSError:
        sock.close()
        raise
    return sock


def usb_stream(sock, token):
    import http.client
    from urllib.parse import urlencode
    from threading import Thread, Event
    stream = http.client.HTTPConnection("127.0.0.1", 8723, timeout=4)
    ack = Event()
    def inputs():
        controls = http.client.HTTPConnection("127.0.0.1", 8723, timeout=4)
        try:
            while True:
                kind, x, y = struct.unpack("!Bff", exact(sock, 9))
                if kind == 0:
                    ack.set()
                    continue
                if kind not in (1, 2, 3) or not (0 <= x <= 1 and 0 <= y <= 1):
                    break
                data = json.dumps(dict(type=("down", "move", "up")[kind-1], x=x, y=y))
                controls.request("POST", "/pointer?" + urlencode({"t": token}), data, {"Content-Type": "application/json"})
                reply = controls.getresponse()
                reply.read()
                if reply.status != 204:
                    break
        except (EOFError, OSError, http.client.HTTPException):
            pass
        finally:
            controls.close()
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            ack.set()
    try:
        if exact(sock, 8) != b"CABPAD12":
            return
        worker = Thread(target=inputs, daemon=True)
        worker.start()
        last = 0
        while worker.is_alive():
            stream.request("GET", "/frame.jpg?" + urlencode({"t": token, "wired": 1, "after": last}))
            res = stream.getresponse()
            data = res.read()
            if res.status not in (200, 204) or len(data) > 16*1024*1024:
                break
            last = int(res.getheader("X-Frame") or last)
            ack.clear()
            sock.sendall(struct.pack("!I", len(data)) + data)
            if not ack.wait(4):
                break
    finally:
        stream.close()


def watch_music():
    folder = DOCS / "music"
    cache = folder / ".cabplay"
    while True:
        try:
            cache.mkdir(parents=True, exist_ok=True)
            catalog = cache / "catalog.json"
            try:
                old = json.loads(catalog.read_text())
            except (OSError, ValueError):
                old = {}
            current = {}
            for file in folder.iterdir():
                if file.name.startswith(".") or file.is_symlink() or not file.is_file() or file.suffix.lower() not in EXTS:
                    continue
                stat = file.stat()
                stamp = [stat.st_size, stat.st_mtime_ns]
                if old.get(file.name, {}).get("stamp") == stamp:
                    current[file.name] = old[file.name]
                    continue
                try:
                    songs, covers = scan(folder, {file.name})
                    song = songs[0]
                    for key, image in covers.items():
                        atomic_write(cache / Path(key).name, image)
                except (ValueError, OSError, IndexError, subprocess.SubprocessError):
                    song = {"file":file.name, "title":file.stem}
                current[file.name] = {"song":song, "stamp":stamp}
            if old != current:
                atomic_write(catalog, encode(current))
        except (OSError, ValueError):
            pass
        time.sleep(3)


def run_usb_worker():
    import http.client
    from threading import Thread
    Thread(target=watch_music, daemon=True).start()
    token_file = ASAR.parents[4] / "Roaming/CabPlay/remote-token.txt"
    while True:
        try:
            token = token_file.read_text().strip()
            with usb_socket() as mux:
                devices = mux_request(mux, {"MessageType": "ListDevices"}).get("DeviceList", [])
            for device in devices:
                if device.get("Properties", {}).get("ConnectionType") != "USB":
                    continue
                with usb_socket() as sock:
                    result = mux_request(sock, dict(MessageType="Connect", DeviceID=device["DeviceID"], PortNumber=socket.htons(USB_PORT)))
                    if result.get("Number") == 0:
                        usb_stream(sock, token)
        except (EOFError, ValueError, OSError, http.client.HTTPException):
            pass
        time.sleep(1)


def configure_usb_agent(enable):
    domain = "gui/" + str(os.getuid())
    if USB_AGENT.exists():
        subprocess.run(["launchctl", "bootout", domain + "/" + USB_LABEL], capture_output=True)
    worker = USB_SUPPORT / "usb-display.py"
    if not enable:
        USB_AGENT.unlink(missing_ok=True)
        worker.unlink(missing_ok=True)
        return
    USB_SUPPORT.mkdir(parents=True, exist_ok=True)
    USB_AGENT.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(worker, Path(__file__).read_bytes())
    atomic_write(USB_AGENT, plistlib.dumps(dict(Label=USB_LABEL, ProgramArguments=[sys.executable, str(worker), "--usb-worker"], KeepAlive=True, RunAtLoad=True, EnvironmentVariables={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})))
    subprocess.run(["launchctl", "bootstrap", domain, str(USB_AGENT)], check=True)


def main():
    if sys.argv[1:] == ["--usb-worker"]:
        return run_usb_worker()
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--restore", action="store_true")
    mode.add_argument("--undo-ultra-texture", action="store_true")
    mode.add_argument("--repair-ultra", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--test-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--archive", type=Path, default=ASAR, help=argparse.SUPPRESS)
    args = parser.parse_args()
    archive = args.archive
    if args.repair_ultra or args.undo_ultra_texture:
        config = Path("/Volumes/HIKVISION/driver/SteamLibrary/steamapps/common/Euro Truck Simulator 2/bin/win_x64/plugins/cabplay.ini")
        return enable_ultra(archive, config, args.undo_ultra_texture)
    backup = archive.with_name("app.asar.before-local-music")
    current = archive.read_bytes()
    header, _ = unpack(current)
    patched = is_patched(header)
    if args.restore:
        if not patched:
            print("当前 CabPlay 没有本地音乐补丁。")
            return
        original = backup.read_bytes()
        oh, od = unpack(original)
        if is_patched(oh) or json.loads(get(oh, od, "package.json"))["version"] != "1.20.2":
            raise ValueError("备份校验失败。")
        if archive.read_bytes() != current:
            raise ValueError("CabPlay 程序文件已变化，请退出后重试。")
        atomic_write(archive, original)
        if archive == ASAR:
            configure_usb_agent(False)
        print("已恢复原版 CabPlay。")
        return

    verify_executable(archive)
    tracks, covers = scan(DOCS / "music")
    original = backup.read_bytes() if patched else current
    program = build(original, tracks, covers)
    if args.test_output:
        with args.test_output.open("xb") as target:
            target.write(program)
    elif not args.check:
        if not patched:
            try:
                with backup.open("xb") as saved:
                    saved.write(original)
            except FileExistsError:
                if backup.read_bytes() != original:
                    raise ValueError("原版文件与旧备份不一致。")
        if archive.read_bytes() != current:
            raise ValueError("CabPlay 程序文件已变化，请退出后重试。")
        atomic_write(archive, program)
        if archive == ASAR:
            configure_usb_agent(True)
    count = sum("cover" in song for song in tracks)
    operation = "验证通过" if args.check or args.test_output else "安装完成"
    print(f"{operation}：{len(tracks)} 首歌，{count} 张可读封面。")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, struct.error, subprocess.SubprocessError) as exc:
        sys.exit(f"操作失败：{exc}")
