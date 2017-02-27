#!powershell
# This file is part of Ansible
#
# Copyright 2014, Trond Hindenes <trond@hindenes.com>
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.


# WANT_JSON
# POWERSHELL_COMMON

$result = @{
    changed = $false
}

$params = Parse-Args $args

$package = Get-AnsibleParam -obj $params -name "name" -type "str" -failifempty $true
$force = Get-AnsibleParam -obj $params -name "force" -type "bool" -default $false
$upgrade = Get-AnsibleParam -obj $params -name "upgrade" -type "bool" -default $false
$version = Get-AnsibleParam -obj $params -name "version" -type "str"
$source = Get-AnsibleParam -obj $params -name "source" -type "str"
$showlog = Get-AnsibleParam -obj $params -name "showlog" -type "bool" -default $false
$state = Get-AnsibleParam -obj $params -name "state" -type "str" -default "present" -validateset "present","absent","latest"
$installargs = Get-AnsibleParam -obj $params -name "install_args" -type "str"
$packageparams = Get-AnsibleParam -obj $params -name "params" -type "str"
$allowemptychecksums = Get-AnsibleParam -obj $params -name "allow_empty_checksums" -type "bool" -default $false
$ignorechecksums = Get-AnsibleParam -obj $params -name "ignore_checksums" -type "bool" -default $false
$ignoredependencies = Get-AnsibleParam -obj $params -name "ignore_dependencies" -type "bool" -default $false

if ($source) {$source = $source.Tolower()}

if ($upgrade)
{
    Add-DeprecateWarning $result "Parameter upgrade=yes is replaced with state=latest"
    if ($state -eq "present")
{
        $state = "latest"
    }
}

# As of chocolatey 0.9.10, nonzero success exit codes can be returned
# See https://github.com/chocolatey/choco/issues/512#issuecomment-214284461
$successexitcodes = (0,1605,1614,1641,3010)

Function Chocolatey-Install-Upgrade
{
    [CmdletBinding()]

    param()

    $ChocoAlreadyInstalled = get-command choco -ErrorAction 0
    if ($ChocoAlreadyInstalled -eq $null)
    {

        #We need to install chocolatey
        $install_output = (new-object net.webclient).DownloadString("https://chocolatey.org/install.ps1") | powershell -
        if ($LASTEXITCODE -ne 0)
        {
            $result.choco_bootstrap_output = $install_output
            Fail-Json $result "Chocolatey bootstrap installation failed."
        }
        $result.changed = $true
        $script:executable = "C:\ProgramData\chocolatey\bin\choco.exe"

    }
    else
    {

        $script:executable = "choco.exe"

        if ([Version](choco --version) -lt [Version]'0.9.9')
        {
            Choco-Upgrade chocolatey
        }

    }
}


Function Choco-IsInstalled
{
    [CmdletBinding()]

    param(
        [Parameter(Mandatory=$true, Position=1)]
        [string]$package
    )

    $cmd = "$executable list --local-only $package"
    $output = invoke-expression $cmd

    $result.rc = $LastExitCode
    if ($LastExitCode -ne 0)
    {
        $result.choco_error_cmd = $cmd
        $result.choco_error_log = $output

        Throw "Error checking installation status for $package"
    }

    If ("$output" -match "(\d+) packages installed.")
    {
        return $matches[1] -gt 0
    }

    return $false
}

Function Choco-Upgrade
{
    [CmdletBinding()]

    param(
        [Parameter(Mandatory=$true, Position=1)]
        [string]$package,
        [Parameter(Mandatory=$false, Position=2)]
        [string]$version,
        [Parameter(Mandatory=$false, Position=3)]
        [string]$source,
        [Parameter(Mandatory=$false, Position=4)]
        [bool]$force,
        [Parameter(Mandatory=$false, Position=5)]
        [string]$installargs,
        [Parameter(Mandatory=$false, Position=6)]
        [string]$packageparams,
        [Parameter(Mandatory=$false, Position=7)]
        [bool]$allowemptychecksums,
        [Parameter(Mandatory=$false, Position=8)]
        [bool]$ignorechecksums,
        [Parameter(Mandatory=$false, Position=9)]
        [bool]$ignoredependencies
    )

    if (-not (Choco-IsInstalled $package))
    {
        throw "$package is not installed, you cannot upgrade"
    }

    $cmd = "$executable upgrade -dv -y $package"

    if ($version)
    {
        $cmd += " -version $version"
    }

    if ($source)
    {
        $cmd += " -source $source"
    }

    if ($force)
    {
        $cmd += " -force"
    }

    if ($installargs)
    {
        $cmd += " -installargs '$installargs'"
    }

    if ($packageparams)
    {
        $cmd += " -params '$packageparams'"
    }

    if ($allowemptychecksums)
    {
        $cmd += " --allow-empty-checksums"
    }

    if ($ignorechecksums)
    {
        $cmd += " --ignore-checksums"
    }

    if ($ignoredependencies)
    {
        $cmd += " -ignoredependencies"
    }

    $output = invoke-expression $cmd

    $result.rc = $LastExitCode
    if ($LastExitCode -notin $successexitcodes)
    {
        $result.choco_error_cmd = $cmd
        $result.choco_error_log = $output
        Throw "Error installing $package"
    }

    if ("$output" -match ' upgraded (\d+)/\d+ package\(s\)\. ')
    {
        if ($matches[1] -gt 0)
        {
            $result.changed = $true
        }
    }
}

Function Choco-Install
{
    [CmdletBinding()]

    param(
        [Parameter(Mandatory=$true, Position=1)]
        [string]$package,
        [Parameter(Mandatory=$false, Position=2)]
        [string]$version,
        [Parameter(Mandatory=$false, Position=3)]
        [string]$source,
        [Parameter(Mandatory=$false, Position=4)]
        [bool]$force,
        [Parameter(Mandatory=$false, Position=5)]
        [bool]$upgrade,
        [Parameter(Mandatory=$false, Position=6)]
        [string]$installargs,
        [Parameter(Mandatory=$false, Position=7)]
        [string]$packageparams,
        [Parameter(Mandatory=$false, Position=8)]
        [bool]$allowemptychecksums,
        [Parameter(Mandatory=$false, Position=9)]
        [bool]$ignorechecksums,
        [Parameter(Mandatory=$false, Position=10)]
        [bool]$ignoredependencies
    )

    if ((Choco-IsInstalled $package) -and -not $force)
    {
        return
    }

    $cmd = "$executable install -dv -y $package"

    if ($version)
    {
        $cmd += " -version $version"
    }

    if ($source)
    {
        $cmd += " -source $source"
    }

    if ($force)
    {
        $cmd += " -force"
    }

    if ($installargs)
    {
        $cmd += " -installargs '$installargs'"
    }

    if ($packageparams)
    {
        $cmd += " -params '$packageparams'"
    }

    if ($allowemptychecksums)
    {
        $cmd += " --allow-empty-checksums"
    }

    if ($ignorechecksums)
    {
        $cmd += " --ignore-checksums"
    }

    if ($ignoredependencies)
    {
        $cmd += " -ignoredependencies"
    }

    $output = invoke-expression $cmd

    $result.rc = $LastExitCode
    if ($LastExitCode -notin $successexitcodes)
    {
        $result.choco_error_cmd = $cmd
        $result.choco_error_log = $output
        Throw "Error installing $package"
    }

    $result.changed = $true
}

Function Choco-Uninstall
{
    [CmdletBinding()]

    param(
        [Parameter(Mandatory=$true, Position=1)]
        [string]$package,
        [Parameter(Mandatory=$false, Position=2)]
        [string]$version,
        [Parameter(Mandatory=$false, Position=3)]
        [bool]$force
    )

    if (-not (Choco-IsInstalled $package))
    {
        return
    }

    $cmd = "$executable uninstall -dv -y $package"

    if ($version)
    {
        $cmd += " -version $version"
    }

    if ($force)
    {
        $cmd += " -force"
    }

    if ($packageparams)
    {
        $cmd += " -params '$packageparams'"
    }

    $output = invoke-expression $cmd

    $result.rc = $LastExitCode
    if ($LastExitCode -notin $successexitcodes)
    {
        $result.choco_error_cmd = $cmd
        $result.choco_error_log = $output
        Throw "Error uninstalling $package"
    }

    $result.changed = $true
}

Try
{
    Chocolatey-Install-Upgrade

    if ($state -eq "present")
    {
        Choco-Install -package $package -version $version -source $source -force $force `
            -installargs $installargs -packageparams $packageparams `
            -allowemptychecksums $allowemptychecksums -ignorechecksums $ignorechecksums `
            -ignoredependencies $ignoredependencies
    }
    elseif ($state -eq "latest")
    {
        Choco-Upgrade -package $package -version $version -source $source -force $force `
            -installargs $installargs -packageparams $packageparams `
            -allowemptychecksums $allowemptychecksums -ignorechecksums $ignorechecksums `
            -ignoredependencies $ignoredependencies
    }
    elseif ($state -eq "absent")
    {
        Choco-Uninstall -package $package -version $version -force $force
    }

    Exit-Json $result
}
Catch
{
    Fail-Json $result $_.Exception.Message
}
