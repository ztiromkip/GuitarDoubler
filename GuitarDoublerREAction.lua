-- USER CONFIG ----------------------------
PYTHON_PATH = "python3"  -- or full path to python
SCRIPT_PATH = "C:/Users/ztiro/Documents/Python Scripts/Guitar Doubler/GuitarDoubler.py"
PARAMS_PATH = "C:/Users/ztiro/Documents/Python Scripts/Guitar Doubler/parameters.json"
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
  params.gain_range,
  params.max_drift_cents,
  params.drift_rate_hz,
  params.overlap_time,
  params.fade_time,
  params.min_shift_time,
  params.max_shift_time,
  array_to_string(params.fc_allpass)
}, ",")

-- show dialog
local retval, inputs = reaper.GetUserInputs(
  "Guitar Doubler Parameters",
  10,
  "Onset Sensitivity,Merge Interval,Gain Range,Max Drift (cents),Drift Rate (Hz),Overlap Time,Fade Time,Min Shift Time,Max Shift Time,Allpass (csv)",
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
params.gain_range = tonumber(vals[3])
params.max_drift_cents = tonumber(vals[4])
params.drift_rate_hz = tonumber(vals[5])
params.overlap_time = tonumber(vals[6])
params.fade_time = tonumber(vals[7])
params.min_shift_time = tonumber(vals[8])
params.max_shift_time = tonumber(vals[9])

-- parse fc_allpass array
params.fc_allpass = {}
for num in string.gmatch(vals[10], "[^,]+") do
  table.insert(params.fc_allpass, tonumber(num))
end

-- write updated JSON
write_file(PARAMS_PATH, json.encode(params, { indent = true }))

-- get selected item
local item = reaper.GetSelectedMediaItem(0, 0)
if not item then
  reaper.ShowMessageBox("No item selected", "Error", 0)
  return
end

local take = reaper.GetActiveTake(item)
local source = reaper.GetMediaItemTake_Source(take)
local _, input_path = reaper.GetMediaSourceFileName(source, "")

-- output file
local output_path = reaper.GetResourcePath() .. "/temp_doubled.wav"

-- run python
local cmd = string.format(
  '"%s" "%s" "%s" "%s"',
  PYTHON_PATH,
  SCRIPT_PATH,
  input_path,
  output_path
)

reaper.ShowConsoleMsg("Running: " .. cmd .. "\n")
os.execute(cmd)

-- insert result on new track at item position
local pos = reaper.GetMediaItemInfo_Value(item, "D_POSITION")

reaper.InsertTrackAtIndex(reaper.CountTracks(0), true)
local new_track = reaper.GetTrack(0, reaper.CountTracks(0)-1)
reaper.SetOnlyTrackSelected(new_track)

reaper.SetEditCurPos(pos, false, false)
reaper.InsertMedia(output_path, 0)

reaper.TrackList_AdjustWindows(false)
reaper.UpdateArrange()