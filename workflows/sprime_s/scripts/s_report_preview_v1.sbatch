#!/bin/bash
#SBATCH --job-name=sconv_report_preview_v1
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-8
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:15:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/logs/s_report_preview_v1_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
task_output=runs/sprime_s_convergence_20261013/reports/current_experiment
pdftotext -f 1 -l 1 "$task_output/report.pdf" "$task_output/first_page.txt"
pdftoppm -f 1 -singlefile -scale-to 1500 -png "$task_output/report.pdf" "$task_output/first_page"
pdfinfo "$task_output/report.pdf"
