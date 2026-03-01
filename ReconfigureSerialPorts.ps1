# Set specified Windows COM port names based on the PNP device properties.
# This allows consistent port configuration even when the serial port
# converters have broken configuration/serials that results in Windows
# reassigning their port numbers on each system boot.
#
# With this script, if the same ports are physically in the same hub
# and port, you can fix them all up with one click.


# --- CONFIGURATION ---

# (Run this script with $printProps = $true + $applyChanges = $false
# to list all props you can use here. Props marked with [!] are the
# most likely to be useful for matching here.)

$testRules = @{
    "COM7" = @{
        "DEVPKEY_Device_LocationInfo" = "Port_#0004.Hub_#0004"
    }
}

$waccaRules = @{
    "COM3" = @{
        "PARENT:DEVPKEY_Device_LocationInfo" = "Port_#0001.Hub_#0002"
    }
    "COM4" = @{
        "PARENT:DEVPKEY_Device_LocationInfo" = "Port_#0002.Hub_#0002"
    }
    "COM6" = @{
        "PARENT:DEVPKEY_Device_LocationInfo" = "Port_#0009.Hub_#0001"
    }
}

# These are the rules we will actually use:
$rules = $testRules

# Print props to match ports on?
$printProps = $true

# Whether to actually apply changes to COM port numbers:
$applyChanges = $false


# --- MISC CONFIGURATION (DON'T CHANGE THIS UNLESS NEEDED) ---

# What port to use as a temporary number for switching
# (Leave $null to find a free port automatically)
$temporaryPort = $null

# We'll look for free ports starting from COM49, COM48, ...
$maxTempComPortNumber = 49

# Most likely names for matching (adds a [!] to the name)
$suggestedPnpPropNames = @(
    "DEVPKEY_Device_Address",
    "DEVPKEY_Device_BiosDeviceName",
    "DEVPKEY_Device_BusNumber",
    "DEVPKEY_Device_FriendlyName",
    "DEVPKEY_Device_HardwareIds",
    "DEVPKEY_Device_InstanceId",
    "DEVPKEY_Device_LocationInfo",
    "DEVPKEY_Device_LocationPaths",
    "DEVPKEY_Device_Parent",
    "DEVPKEY_Device_PhysicalDeviceLocation",
    "DEVPKEY_Device_Stack",
    "DEVPKEY_NAME"
)

# Some PNP props are useless for matching, ignore them to minimize noise:
$excludedPnpPropNames = @(
    "DEVPKEY_Device_HasProblem",
    "DEVPKEY_Device_PowerData"
)


# --- SCRIPT ---

function Format-Object($object) {
    $typeName = $object.GetType().Name
    if ($typeName -eq "String[]") {
        return "[string[]](`"" + [System.String]::Join("`", `"", $object) + "`")"
    } elseif ($typeName -eq "String") {
        return "`"$object`""
    } elseif ($typeName -eq "Byte[]") {
        return "[byte[]](" + [System.String]::Join(", ", $object) + ")"
    } elseif ($typeName -eq "Boolean") {
        if ($object) {
            return "`$true"
        } else {
            return "`$false"
        }
    } else {
        return ($object | Out-String).Trim()
    }
}

# https://stackoverflow.com/a/7475744
function Clone-Object($object) {
    $memStream = New-Object IO.MemoryStream
    $formatter = New-Object Runtime.Serialization.Formatters.Binary.BinaryFormatter
    $formatter.Serialize($memStream, $object)
    $memStream.Position = 0
    return $formatter.Deserialize($memStream)
}

function Get-PortName($pnpDeviceId) {
    $deviceKey = "HKLM:\SYSTEM\CurrentControlSet\Enum\$pnpDeviceId"
    $portKey = "$deviceKey\Device Parameters"

    $name = Get-ItemProperty -Path $portKey -Name "PortName" -ErrorAction SilentlyContinue
    $label = Get-ItemProperty -Path $deviceKey -Name "FriendlyName" -ErrorAction SilentlyContinue
    if ($name -eq $null -or $label -eq $null) {
        return $null, $null
    }

    return $name.PortName, $label.FriendlyName
}

function Set-PortName($pnpDeviceId, $comPort, $friendlyName = $null) {
    Write-Host "Setting PNP device" $pnpDeviceId "to COM Port" $comPort
    $deviceKey = "HKLM:\SYSTEM\CurrentControlSet\Enum\$pnpDeviceId"
    $portKey = "$deviceKey\Device Parameters"

    $friendlyName = Get-ItemProperty -Path $deviceKey -Name "FriendlyName" -ErrorAction SilentlyContinue
    $existingPortName = Get-ItemProperty -Path $portKey -Name "PortName" -ErrorAction SilentlyContinue

    if ($existingPortName -eq $null) {
        throw "Tried to set a COM port name for $pnpDeviceId but device does not have a PortName registry key value"
    }

    if ($comPort -notmatch 'COM\d+') {
        throw "Tried to set an invalid COM port name $comPort for $pnpDeviceId"
    }

    if ($friendlyName -eq $null) {
        $friendlyName = "Serial Port ($comPort)"
    }

    Disable-PnpDevice -InstanceId $pnpDeviceId -Confirm:$false
    Set-ItemProperty -Path $deviceKey -Name "FriendlyName" -Value "Serial Port ($comPort)" -ErrorAction Stop
    Set-ItemProperty -Path $portKey -Name "PortName" -Value $comPort -ErrorAction Stop
    Enable-PnpDevice -InstanceId $pnpDeviceId -Confirm:$false
}

function Build-Props($pnpDeviceId, $prefix = "") {
    $props = @{}
    $prettyProps = @{}
    foreach ($pnpProp in (Get-PnpDeviceProperty -InstanceId $pnpDeviceId)) {
        if ($pnpProp.KeyName -in $excludedPnpPropNames) { continue; }
        if ($pnpProp.Data.GetType().Name -eq "DateTime") { continue; }

        $prettyName = $pnpProp.KeyName
        if ($prettyName -in $suggestedPnpPropNames) {
            $prettyName = "[!] $prettyName"
        }

        $props[$prefix + $pnpProp.KeyName] = $pnpProp.Data
        $prettyProps[$prefix + $pnpProp.KeyName] = Format-Object $pnpProp.Data
    }

    return $props, $prettyProps
}

function Reconfigure-Ports {
    # Get the COM port details for all serial ports
    $pnpDevices = Get-WmiObject Win32_PnPEntity

    $discoveredPorts = @{}
    $wantedPorts = @{}

    foreach ($pnpDevice in $pnpDevices) {
        $pnpDeviceId = $pnpDevice.PNPDeviceID
        $comPort, $friendlyName = Get-PortName $pnpDeviceId
        if ($comPort -eq $null) { continue; }

        $discoveredPorts[$comPort] = $pnpDeviceId
        Write-Host "# Candidate:" $pnpDeviceId "|" $friendlyName "|" $comPort

        $props, $prettyProps = Build-Props $pnpDeviceId
        $parentPnpDeviceId = $props["DEVPKEY_Device_Parent"]
        if ($parentPnpDeviceId) {
            Write-Host "Also parsing parent device $parentPnpDeviceId"
            $parentProps, $parentPrettyProps = Build-Props $parentPnpDeviceId "PARENT:"
            $props = $props + $parentProps
            $prettyProps = $prettyProps + $parentPrettyProps
        }

        if ($printProps) {
            $prettyProps | Format-Table -AutoSize
        }

        $matchedPort = $null
        $candidates = Clone-Object $rules
        foreach ($prop in $props.GetEnumerator()) {
            $removeCandidate = $null;
            foreach ($candidate in $candidates.GetEnumerator()) {
                $candidatePort = $candidate.Name
                $candidateRules = $candidate.Value

                $candidateRule = $candidate.Value[$prop.Name]
                if ($candidateRule) {
                    Write-Host "[?]" $prop.Name "(has:" $prop.Value "- wants:" $candidateRule ")"
                    if ($candidateRule -eq $prop.Value) {
                        Write-Host "Matched, removing required rule"
                        $candidateRules.Remove($prop.Name)
                    } else {
                        Write-Host "Mismatch, removing port $candidatePort from candidates"
                        $removeCandidate = $candidatePort
                        continue;
                    }
                }

                if ($candidateRules.Count -eq 0) {
                    Write-Host "[!] Matched: $candidatePort is $pnpDeviceId"
                    $matchedPort = $candidatePort
                    break;
                }
            }

            if ($removeCandidate) {
                $candidates.Remove($removeCandidate)
            }

            if ($matchedPort) {
                $wantedPorts[$matchedPort] = $pnpDeviceId
                $rules.Remove($matchedPort)
                break;
            }
        }

    }

    Write-Host "Discovered Ports:"
    $discoveredPorts | Format-Table -AutoSize

    Write-Host "Wanted Ports:"
    $wantedPorts | Format-Table -AutoSize

    if ($temporaryPort -eq $null) {
        foreach ($number in $maxTempComPortNumber..1) {
            if ("COM$number" -notin $discoveredPorts) {
                $temporaryPort = "COM$number"
                break;
            }
        }

        if ($temporaryPort -eq $null) {
            throw "Cannot allocate a free temporary port!"
        }

        if ($temporaryPort -in $discoveredPorts) {
            throw "Chosen temporary port is already in use!"
        }
    }

    Write-Host "Chosen temporary port number:" $temporaryPort

    if (!$applyChanges) {
        Write-Host "Not applying changes, bye!"
        return
    }

    Write-Host "Applying changes..."
    foreach ($wanted in $wantedPorts.GetEnumerator()) {
        $targetPortName = $wanted.Name
        $targetDevice = $wanted.Value

        $currentPortName, $currentFriendlyName = Get-PortName $targetDevice

        if ($targetPortName -eq $currentPortName) {
            Write-Host $targetPortName "is already configured correctly"
            continue;
        }

        if ($targetPortName -notin $discoveredPorts.Keys) {
            Set-PortName $targetDevice $targetPortName $null
            if ($currentPortName -in $discoveredPorts) {
                $discoveredPorts.Remove($currentPortName)
            }

            $discoveredPorts[$targetPortName] = $targetDevice
        } else {
            # Swap with current:
            $conflictingDevice = $discoveredPorts[$targetPortName]
            Set-PortName $conflictingDevice $temporaryPort $null
            Set-PortName $targetDevice $targetPortName $null
            Set-PortName $conflictingDevice $currentPortName $null

            $discoveredPorts[$targetPortName] = $targetDevice
            $discoveredPorts[$currentPortName] = $conflictingDevice
        }
    }
}

Reconfigure-Ports
