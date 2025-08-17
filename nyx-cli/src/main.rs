use anyhow::Result;
use std::env;
use std::process::Command;

fn main() -> Result<()> {
    let args: Vec<String> = env::args().collect();

    if args.len() < 2 {
        eprintln!("Usage: nyx <prompt>");
        eprintln!("Example: nyx \"create a file named hello.txt with the content 'hello world'\"");
        return Ok(());
    }

    // Join all arguments after the program name into a single prompt string
    let prompt = &args[1..].join(" ");

    let output = Command::new("python3")
        .arg("../agents/main_agent.py")
        .arg(prompt)
        .output()?;

    if output.status.success() {
        println!("{}", String::from_utf8_lossy(&output.stdout));
    } else {
        eprintln!("{}", String::from_utf8_lossy(&output.stderr));
    }

    Ok(())
}
