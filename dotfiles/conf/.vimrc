"        _
" __   _(_)_ __ ___  _ __ ___
" \ \ / / | '_ ` _ \| '__/ __|
"  \ V /| | | | | | | | | (__
"   \_/ |_|_| |_| |_|_|  \___|
"
" Ryan's .vimrc file
"
"--------------------------------------------------------------------------

command! TEOL %s/[\t ]\+$//g
command! W w
command! Q q

filetype indent plugin on
filetype plugin on

imap <C-a> <Home>
imap <C-e> <End>

match Error /\s\+$/

nmap <Enter> o<Esc>k

noremap - <C-z>

set expandtab
set history=200
set hlsearch
set incsearch
set nobackup
set nowritebackup
set shiftwidth=4
set smartcase
set softtabstop=4
set tabstop=4

set swapfile
set dir=/tmp

syntax on
