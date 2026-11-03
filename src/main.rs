//! SigmaOS-desktop - SigmaOS Component CLI
//!
//! Command-line interface for SigmaOS-desktop component.

use anyhow::Result;
use clap::{Parser, Subcommand};
use log::info;
use desktop::{Component, ComponentStatus, Config, desktop};

#[derive(Parser)]
#[command(name = "desktop")]
#[command(about = "SigmaOS SigmaOS-desktop component", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Initialize the component
    Init {
        /// Enable debug mode
        #[arg(short, long)]
        debug: bool,
    },
    /// Start the component
    Start,
    /// Stop the component
    Stop,
    /// Get component status
    Status,
    /// Run the component
    Run {
        /// Enable debug mode
        #[arg(short, long)]
        debug: bool,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    
    let config = Config::default();
    let mut component = desktop::new(config);

    match cli.command {
        Commands::Init { debug } => {
            if debug {
                println!("Initializing SigmaOS-desktop in debug mode...");
            } else {
                println!("Initializing SigmaOS-desktop...");
            }
            component.initialize()?;
            println!("SigmaOS-desktop initialized successfully");
        }
        Commands::Start => {
            component.initialize()?;
            component.start()?;
            println!("SigmaOS-desktop started successfully");
        }
        Commands::Stop => {
            component.stop()?;
            println!("SigmaOS-desktop stopped successfully");
        }
        Commands::Status => {
            let status = component.status();
            println!("SigmaOS-desktop status: {:?}", status);
        }
        Commands::Run { debug } => {
            if debug {
                println!("Running SigmaOS-desktop in debug mode...");
            } else {
                println!("Running SigmaOS-desktop...");
            }
            component.initialize()?;
            component.start()?;
            println!("SigmaOS-desktop is running. Press Ctrl+C to stop.");
            
            // Keep running
            tokio::runtime::Runtime::new()?.block_on(async {
                tokio::signal::ctrl_c().await.unwrap();
                info!("Received Ctrl+C, shutting down...");
            });
            
            component.stop()?;
            println!("SigmaOS-desktop stopped");
        }
    }

    Ok(())
}
