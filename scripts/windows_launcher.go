//go:build windows

// A small native launcher. Python and all application files stay inspectable.
package main

import (
    "bufio"
    "fmt"
    "io"
    "os"
    "os/exec"
    "os/signal"
    "path/filepath"
    "syscall"
    "unsafe"
)

func fail(err error) {
    fmt.Println("Could not start BMW Product Intelligence:", err)
    fmt.Println("Extract the complete ZIP to a writable folder, then try again.")
    fmt.Println("Press Enter to close.")
    bufio.NewReader(os.Stdin).ReadString('\n')
    os.Exit(1)
}

func main() {
    exe, err := os.Executable()
    if err != nil { fail(err) }
    root := filepath.Dir(exe)
    python := filepath.Join(root, "runtime", "python", "python.exe")
    script := filepath.Join(root, "app", "scripts", "portable_server.py")
    for _, file := range []string{python, script, filepath.Join(root, "web", "index.html")} {
        if _, err := os.Stat(file); err != nil { fail(err) }
    }
    log, err := os.OpenFile(filepath.Join(root, "startup.log"), os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0600)
    if err != nil { fail(err) }
    defer log.Close()
    cmd := exec.Command(python, append([]string{"-u", script}, os.Args[1:]...)...)
    cmd.Dir = filepath.Join(root, "app")
    cmd.Stdin = os.Stdin
    cmd.Stdout = io.MultiWriter(os.Stdout, log)
    cmd.Stderr = io.MultiWriter(os.Stderr, log)

    // Windows closes the job when this console closes, stopping the API and
    // any collection subprocesses instead of leaving background servers.
    kernel := syscall.NewLazyDLL("kernel32.dll")
    job, _, jobErr := kernel.NewProc("CreateJobObjectW").Call(0, 0)
    if job == 0 { fail(jobErr) }
    defer syscall.CloseHandle(syscall.Handle(job))
    limits := [144]byte{} // JOBOBJECT_EXTENDED_LIMIT_INFORMATION on Windows x64.
    *(*uint32)(unsafe.Pointer(&limits[16])) = 0x2000 // KILL_ON_JOB_CLOSE
    ok, _, setErr := kernel.NewProc("SetInformationJobObject").Call(job, 9, uintptr(unsafe.Pointer(&limits[0])), uintptr(len(limits)))
    if ok == 0 { fail(setErr) }
    if err := cmd.Start(); err != nil { fail(err) }
    handle, err := syscall.OpenProcess(0x0101, false, uint32(cmd.Process.Pid))
    if err != nil { cmd.Process.Kill(); fail(err) }
    ok, _, assignErr := kernel.NewProc("AssignProcessToJobObject").Call(job, uintptr(handle))
    syscall.CloseHandle(handle)
    if ok == 0 { cmd.Process.Kill(); fail(assignErr) }

    // Python receives Ctrl+C from the same console and shuts down gracefully.
    interrupts := make(chan os.Signal, 1)
    signal.Notify(interrupts, os.Interrupt)
    defer signal.Stop(interrupts)
    if err := cmd.Wait(); err != nil {
        select { case <-interrupts: return; default: fail(err) }
    }
}
