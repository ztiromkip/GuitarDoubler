-- USER CONFIG ----------------------------
local info = debug.getinfo(1, "S")
local script_path = info.source:match("@(.*[\\/])")

PYTHON_PATH = script_path .. ".venv\\Scripts\\python.exe"
SCRIPT_PATH = script_path .. "GuitarDoubler.py"
PARAMS_PATH = script_path .. "parameters.json"
------------------------------------------

-- load dkjson
local json = dofile(reaper.GetResourcePath() .. "/Scripts/dkjson.lua")

-- file helpers
function read_file(path)
  local f = io.open(path, "r")
  if not f then return nil end
  local content = f:read("*all")
  f:close()
  return content
end

function write_file(path, content)
  local f = io.open(path, "w")
  f:write(content)
  f:close()
end

-- load parameters
local raw = read_file(PARAMS_PATH)
if not raw then
  reaper.ShowMessageBox("Could not read parameters.json", "Error", 0)
  return
end

local params, _, err = json.decode(raw)
if err then
  reaper.ShowMessageBox("JSON parse error: " .. err, "Error", 0)
  return
end

-- convert fc_allpass array to string
local function array_to_string(arr)
  local t = {}
  for i=1,#arr do
    t[#t+1] = tostring(arr[i])
  end
  return table.concat(t, ",")
end

-- dialog defaults
local defaults = table.concat({
  params.onset_sensitivity,
  params.merge_interval_time,
  params.max_shift_cents,
  params.max_drift_cents,
  params.drift_rate_hz,
  params.overlap_time,
  params.fade_time,
  params.min_shift_time,
  params.max_shift_time,
  params.gain_range
  -- array_to_string(params.fc_allpass)
}, ",")

-- show dialog
local retval, inputs = reaper.GetUserInputs(
  "Guitar Doubler Parameters",
  10,
  "Onset Sensitivity,Merge Interval Time,Max Shift Cents,Max Drift Cents,Drift Rate Hz,Overlap Time,Fade Time,Min Shift Time,Max Shift Time,Gain Range",
  defaults
)

if not retval then return end

-- parse inputs
local vals = {}
for v in string.gmatch(inputs, "([^,]+)") do
  vals[#vals+1] = v
end

-- update parameters
params.onset_sensitivity = tonumber(vals[1])
params.merge_interval_time = tonumber(vals[2])
params.max_shift_cents = tonumber(vals[3])
params.max_drift_cents = tonumber(vals[4])
params.drift_rate_hz = tonumber(vals[5])
params.overlap_time = tonumber(vals[6])
params.fade_time = tonumber(vals[7])
params.min_shift_time = tonumber(vals[8])
params.max_shift_time = tonumber(vals[9])
params.gain_range = tonumber(vals[10])

-- write updated JSON
write_file(PARAMS_PATH, json.encode(params, {
  indent = true,
  keyorder = {
      "onset_sensitivity",
      "plot_onsets",
      "merge_interval_time",
      "max_shift_cents",
      "max_drift_cents",
      "drift_rate_hz",
      "overlap_time",
      "fade_time",
      "min_shift_time",
      "max_shift_time",
      "gain_range",
      "fc_allpass"
  }
}))

local item = reaper.GetSelectedMediaItem(0, 0)
if not item then
  reaper.ShowMessageBox("No item selected", "Error", 0)
  return
end

local take = reaper.GetActiveTake(item)
if not take then
  reaper.ShowMessageBox("No active take", "Error", 0)
  return
end

if not take then
  reaper.ShowMessageBox("No active take (item might be MIDI or empty)", "Error", 0)
  return
end

local source = reaper.GetMediaItemTake_Source(take)
local input_path = reaper.GetMediaSourceFileName(source, "")

if not input_path or input_path == "" then
  reaper.ShowMessageBox("Could not get item file path", "Error", 0)
  return
end

-- build output path
local function get_dir(path)
  return path:match("^(.*[\\/])")
end

local function get_filename(path)
  return path:match("([^\\/]+)$")
end

local dir = get_dir(input_path)
local name = get_filename(input_path)
local base = name:match("(.+)%..+$") or name
local output_path = dir .. base .. "_doubled.wav"

-- run python with logging
local log_path = reaper.GetResourcePath() .. "/python_log.txt"

local cmd = string.format(
  'cmd.exe /C ""%s" "%s" "%s" "%s" > "%s" 2>&1"',
  PYTHON_PATH,
  SCRIPT_PATH,
  input_path,
  output_path,
  log_path
)

reaper.ShowConsoleMsg("Running: " .. cmd .. "\n")
os.execute(cmd)

-- verify output
local f = io.open(output_path, "r")
if not f then
  reaper.ShowMessageBox("Output file not created. Check python_log.txt", "Error", 0)
  return
end
f:close()

-- insert
local pos = reaper.GetMediaItemInfo_Value(item, "D_POSITION")

reaper.InsertTrackAtIndex(reaper.CountTracks(0), true)
local new_track = reaper.GetTrack(0, reaper.CountTracks(0)-1)
reaper.SetOnlyTrackSelected(new_track)

reaper.SetEditCurPos(pos, false, false)
reaper.InsertMedia(output_path, 0)

reaper.UpdateArrange()