#!/usr/bin/env node
import { Command } from "commander";

const program = new Command();
program.name("crawfish-projectctl").version("0.1.0");
program.parse();
