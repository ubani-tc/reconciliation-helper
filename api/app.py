from flask import Flask, request, jsonify, send_file, render_template_string
import pandas as pd
import os
import io
import json
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import numpy as np

app = Flask(__name__)

# Store data in memory with currency and module support
reconciliation_data = {
    'collections': {
        'UGX': {'internal': [], 'processors': {}, 'processor_data': []},
        'NGN': {'internal': [], 'processors': {}, 'processor_data': []},
        'TZS': {'internal': [], 'processors': {}, 'processor_data': []},
        'KES': {'internal': [], 'processors': {}, 'processor_data': []},
        'GHS': {'internal': [], 'processors': {}, 'processor_data': []},
        'ZMW': {'internal': [], 'processors': {}, 'processor_data': []},
        'ZAR': {'internal': [], 'processors': {}, 'processor_data': []}
    },
    'payouts': {
        'UGX': {'internal': [], 'processors': {}, 'processor_data': []},
        'NGN': {'internal': [], 'processors': {}, 'processor_data': []},
        'TZS': {'internal': [], 'processors': {}, 'processor_data': []},
        'KES': {'internal': [], 'processors': {}, 'processor_data': []},
        'GHS': {'internal': [], 'processors': {}, 'processor_data': []},
        'ZMW': {'internal': [], 'processors': {}, 'processor_data': []},
        'ZAR': {'internal': [], 'processors': {}, 'processor_data': []}
    },
    'fund_transfers': {
        'UGX': {'internal': [], 'processors': {}, 'processor_data': []},
        'NGN': {'internal': [], 'processors': {}, 'processor_data': []},
        'TZS': {'internal': [], 'processors': {}, 'processor_data': []},
        'KES': {'internal': [], 'processors': {}, 'processor_data': []},
        'GHS': {'internal': [], 'processors': {}, 'processor_data': []},
        'ZMW': {'internal': [], 'processors': {}, 'processor_data': []},
        'ZAR': {'internal': [], 'processors': {}, 'processor_data': []}
    }
}

# Store reconciliation history
reconciliation_history = []

# Helper function to format numbers with commas
def format_currency(amount):
    """Format amount with thousand separators"""
    try:
        return f"{float(amount):,.2f}"
    except (ValueError, TypeError):
        return "0.00"

# Optimized matching function
def find_matches_optimized(internal_data, processor_data):
    """Optimized matching for large datasets"""
    matches = []
    matched_references = set()
    
    # Create lookup dictionaries for faster access
    internal_lookup = {}
    for internal in internal_data:
        ref = str(internal['reference_number']).strip()
        internal_lookup[ref] = internal
    
    processor_lookup = {}
    for processor in processor_data:
        ref = str(processor['reference_number']).strip()
        if ref not in processor_lookup:
            processor_lookup[ref] = []
        processor_lookup[ref].append(processor)
    
    # Find matches
    for ref, internal in internal_lookup.items():
        if ref in processor_lookup:
            for processor in processor_lookup[ref]:
                if abs(float(internal['amount']) - float(processor['amount'])) < 0.01:
                    match_type = "exact" if internal['amount'] == processor['amount'] else "within_tolerance"
                    matches.append({
                        'reference': ref,
                        'internal_amount': float(internal['amount']),
                        'processor_amount': float(processor['amount']),
                        'processor': processor['processor_name'],
                        'match_type': match_type,
                        'currency': internal.get('currency', '')
                    })
                    matched_references.add(ref)
                    break
    
    return matches, matched_references

# Calculate overall statistics
def get_overall_statistics():
    """Get overall statistics for all modules and currencies"""
    total_reconciliations = len(reconciliation_history)
    
    total_matched = 0
    total_unmatched_internal = 0
    total_unmatched_processor = 0
    
    for recon in reconciliation_history:
        total_matched += recon.get('matched_count', 0)
        total_unmatched_internal += recon.get('unmatched_internal_count', 0)
        total_unmatched_processor += recon.get('unmatched_processor_count', 0)
    
    return {
        'total_reconciliations': total_reconciliations,
        'total_matched': total_matched,
        'total_unmatched_internal': total_unmatched_internal,
        'total_unmatched_processor': total_unmatched_processor
    }

# HTML for the landing page
LANDING_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Reconciliation Platform</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary: #4361ee;
            --secondary: #3a56d4;
            --success: #28a745;
            --danger: #dc3545;
            --warning: #ffc107;
            --info: #17a2b8;
            --light: #f8f9fa;
            --dark: #343a40;
            --gray: #6c757d;
            --border: #dee2e6;
            --card-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            --hover-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #f8f9fa;
            min-height: 100vh;
            color: var(--dark);
            font-size: 14px;
            padding: 10px;
        }

        .dashboard-container {
            max-width: 1200px;
            margin: 0 auto;
        }

        .header {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: var(--card-shadow);
            text-align: center;
        }

        .header h1 {
            color: var(--primary);
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 8px;
        }

        .header p {
            color: var(--gray);
            font-size: 0.95rem;
            margin-bottom: 15px;
        }

        .modules-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .module-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: var(--card-shadow);
            border: 1px solid var(--border);
            transition: all 0.3s ease;
            text-align: center;
            cursor: pointer;
        }

        .module-card:hover {
            transform: translateY(-3px);
            box-shadow: var(--hover-shadow);
        }

        .module-icon {
            font-size: 2.2rem;
            margin-bottom: 15px;
            color: var(--primary);
        }

        .module-card h2 {
            color: var(--primary);
            font-size: 1.3rem;
            margin-bottom: 10px;
        }

        .module-card p {
            color: var(--gray);
            margin-bottom: 15px;
            font-size: 0.9rem;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }

        .stat-card {
            background: white;
            padding: 15px;
            border-radius: 6px;
            box-shadow: var(--card-shadow);
            text-align: center;
            border-left: 4px solid var(--primary);
        }

        .stat-card.total { border-left-color: var(--primary); }
        .stat-card.matched { border-left-color: var(--success); }
        .stat-card.unmatched { border-left-color: var(--warning); }

        .stat-icon {
            font-size: 1.5rem;
            margin-bottom: 10px;
            color: var(--primary);
        }

        .stat-card.matched .stat-icon { color: var(--success); }
        .stat-card.unmatched .stat-icon { color: var(--warning); }

        .stat-number {
            font-size: 1.5rem;
            font-weight: 700;
            margin: 8px 0;
        }

        .stat-label {
            color: var(--gray);
            font-size: 0.8rem;
            text-transform: uppercase;
        }

        .btn {
            background: var(--primary);
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }

        .btn:hover {
            background: var(--secondary);
            transform: translateY(-1px);
        }

        .hidden {
            display: none;
        }

        .currency-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 12px;
            margin: 15px 0;
        }

        .currency-card {
            background: white;
            padding: 15px;
            border-radius: 6px;
            box-shadow: var(--card-shadow);
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            border: 2px solid transparent;
        }

        .currency-card:hover {
            border-color: var(--primary);
            transform: translateY(-1px);
        }

        .currency-card.selected {
            border-color: var(--primary);
            background: rgba(67, 97, 238, 0.05);
        }

        .back-btn {
            background: var(--gray);
            margin-bottom: 15px;
            padding: 8px 15px;
        }

        .back-btn:hover {
            background: #5a6268;
        }

        .upload-section {
            background: white;
            padding: 15px;
            border-radius: 6px;
            box-shadow: var(--card-shadow);
            margin-bottom: 15px;
        }

        .upload-section h3 {
            color: var(--primary);
            margin-bottom: 15px;
            font-size: 1.1rem;
        }

        .file-drop-area {
            border: 2px dashed var(--border);
            padding: 15px;
            border-radius: 6px;
            text-align: center;
            margin: 10px 0;
            background: var(--light);
        }

        .form-group {
            margin-bottom: 12px;
        }

        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: var(--dark);
        }

        .form-control {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 14px;
        }

        .processor-list {
            background: var(--light);
            padding: 12px;
            border-radius: 6px;
            margin: 10px 0;
            display: none;
        }

        .processor-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px;
            background: white;
            margin: 5px 0;
            border-radius: 4px;
            border: 1px solid var(--border);
        }

        .message {
            padding: 8px 12px;
            border-radius: 4px;
            margin-top: 8px;
            font-size: 0.9rem;
        }

        .message.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .message.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .message.warning { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- Landing Page -->
        <div id="landingPage">
            <div class="header">
                <h1><i class="fas fa-exchange-alt"></i> Reconciliation Platform</h1>
                <p>Comprehensive reconciliation for Collections, Payouts, and Fund Transfers across 7 currencies</p>
            </div>

            <div class="stats-grid">
                <div class="stat-card total">
                    <i class="fas fa-chart-bar stat-icon"></i>
                    <div class="stat-number" id="totalReconciliations">0</div>
                    <div class="stat-label">Total Reconciliations</div>
                </div>
                <div class="stat-card matched">
                    <i class="fas fa-check-circle stat-icon"></i>
                    <div class="stat-number" id="totalMatched">0</div>
                    <div class="stat-label">Total Matched</div>
                </div>
                <div class="stat-card unmatched">
                    <i class="fas fa-exclamation-triangle stat-icon"></i>
                    <div class="stat-number" id="totalUnmatched">0</div>
                    <div class="stat-label">Total Unmatched</div>
                </div>
            </div>

            <div class="modules-grid">
                <div class="module-card" onclick="showModule('collections')">
                    <i class="fas fa-cash-register module-icon"></i>
                    <h2>Collections Reconciliation</h2>
                    <p>Reconcile payment collections across all currencies</p>
                    <div class="btn">Select Module</div>
                </div>

                <div class="module-card" onclick="showModule('payouts')">
                    <i class="fas fa-money-check-alt module-icon"></i>
                    <h2>Payouts Reconciliation</h2>
                    <p>Reconcile merchant payouts and disbursements</p>
                    <div class="btn">Select Module</div>
                </div>

                <div class="module-card" onclick="showModule('fund_transfers')">
                    <i class="fas fa-exchange-alt module-icon"></i>
                    <h2>Fund Transfers Reconciliation</h2>
                    <p>Reconcile internal fund transfers and settlements</p>
                    <div class="btn">Select Module</div>
                </div>
            </div>
        </div>

        <!-- Currency Selection Page -->
        <div id="currencyPage" class="hidden">
            <button class="btn back-btn" onclick="showLandingPage()">
                <i class="fas fa-arrow-left"></i> Back to Modules
            </button>
            
            <div class="header">
                <h1 id="moduleTitle">Module</h1>
                <p>Select currency for reconciliation</p>
            </div>

            <div class="currency-grid">
                <div class="currency-card" onclick="selectCurrency('UGX')">
                    <h3>UGX</h3>
                    <p>Ugandan Shilling</p>
                </div>
                <div class="currency-card" onclick="selectCurrency('NGN')">
                    <h3>NGN</h3>
                    <p>Nigerian Naira</p>
                </div>
                <div class="currency-card" onclick="selectCurrency('TZS')">
                    <h3>TZS</h3>
                    <p>Tanzanian Shilling</p>
                </div>
                <div class="currency-card" onclick="selectCurrency('KES')">
                    <h3>KES</h3>
                    <p>Kenyan Shilling</p>
                </div>
                <div class="currency-card" onclick="selectCurrency('GHS')">
                    <h3>GHS</h3>
                    <p>Ghanaian Cedi</p>
                </div>
                <div class="currency-card" onclick="selectCurrency('ZMW')">
                    <h3>ZMW</h3>
                    <p>Zambian Kwacha</p>
                </div>
                <div class="currency-card" onclick="selectCurrency('ZAR')">
                    <h3>ZAR</h3>
                    <p>South African Rand</p>
                </div>
            </div>
        </div>

        <!-- Reconciliation Dashboard -->
        <div id="reconciliationPage" class="hidden">
            <button class="btn back-btn" onclick="showCurrencyPage()">
                <i class="fas fa-arrow-left"></i> Back to Currencies
            </button>
            
            <div class="header">
                <h1 id="reconTitle">Reconciliation</h1>
                <p id="reconSubtitle">Module • Currency</p>
            </div>

            <!-- Upload Sections -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                <!-- Internal Report Upload -->
                <div class="upload-section">
                    <h3><i class="fas fa-building"></i> Internal Report</h3>
                    <div class="form-group">
                        <label>Report Type</label>
                        <select id="internalReportType" class="form-control" onchange="toggleInternalCustom()">
                            <option value="">Select Report Type</option>
                            <option value="standard">Standard Internal Report</option>
                            <option value="bank_statement">Bank Statement</option>
                            <option value="general_ledger">General Ledger</option>
                            <option value="custom">Custom Format</option>
                        </select>
                    </div>
                    
                    <div id="internalCustomFields" style="display: none;">
                        <div class="form-group">
                            <label>Reference Column</label>
                            <input type="text" id="internalRefColumn" class="form-control" placeholder="e.g., reference_number">
                        </div>
                        <div class="form-group">
                            <label>Amount Column</label>
                            <input type="text" id="internalAmountColumn" class="form-control" placeholder="e.g., amount">
                        </div>
                    </div>

                    <div class="file-drop-area">
                        <input type="file" id="internalFile" style="display: none;" accept=".csv,.xlsx,.xls">
                        <label for="internalFile" class="btn" style="display: block; margin: 8px 0;">
                            <i class="fas fa-file-upload"></i> Choose File
                        </label>
                        <div id="internalFileName" style="color: var(--gray); font-size: 0.9rem;">No file chosen</div>
                    </div>
                    <button onclick="uploadFile('internal')" class="btn" style="width: 100%;">
                        <i class="fas fa-upload"></i> Upload Internal Report
                    </button>
                    <div id="internalMessage"></div>
                </div>

                <!-- Processor Reports Upload -->
                <div class="upload-section">
                    <h3><i class="fas fa-credit-card"></i> Processor Reports</h3>
                    
                    <div class="form-group">
                        <label>Processor Type</label>
                        <select id="processorType" class="form-control" onchange="toggleProcessorCustom()">
                            <option value="">Select Processor Type</option>
                            <option value="mpesa">M-Pesa</option>
                            <option value="airtel_money">Airtel Money</option>
                            <option value="mtn_momo">MTN MoMo</option>
                            <option value="paystack">Paystack</option>
                            <option value="flutterwave">Flutterwave</option>
                            <option value="stripe">Stripe</option>
                            <option value="custom">Custom Processor</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label>Processor Name</label>
                        <input type="text" id="processorName" class="form-control" placeholder="Enter processor name">
                    </div>

                    <div id="processorCustomFields" style="display: none;">
                        <div class="form-group">
                            <label>Reference Column</label>
                            <input type="text" id="processorRefColumn" class="form-control" placeholder="e.g., reference_number">
                        </div>
                        <div class="form-group">
                            <label>Amount Column</label>
                            <input type="text" id="processorAmountColumn" class="form-control" placeholder="e.g., amount">
                        </div>
                    </div>

                    <div id="processorList" class="processor-list">
                        <h4 style="margin-bottom: 8px; font-size: 0.9rem;"><i class="fas fa-list"></i> Uploaded Processors</h4>
                        <div id="processorItems"></div>
                    </div>

                    <div class="file-drop-area">
                        <input type="file" id="processorFile" style="display: none;" accept=".csv,.xlsx,.xls" multiple>
                        <label for="processorFile" class="btn" style="display: block; margin: 8px 0;">
                            <i class="fas fa-file-upload"></i> Choose Files
                        </label>
                        <div id="processorFileName" style="color: var(--gray); font-size: 0.9rem;">No files chosen</div>
                    </div>
                    <button onclick="uploadFile('processor')" class="btn" style="width: 100%;">
                        <i class="fas fa-upload"></i> Upload Processor Report(s)
                    </button>
                    <div id="processorMessage"></div>
                </div>
            </div>

            <!-- Action Section -->
            <div class="upload-section">
                <h3><i class="fas fa-play-circle"></i> Run Reconciliation</h3>
                <button onclick="runReconciliation()" class="btn" style="width: 100%; padding: 12px; background: var(--success);">
                    <i class="fas fa-cogs"></i> Start Reconciliation Process
                </button>
                
                <div id="results">
                    <div style="text-align: center; padding: 30px; color: var(--gray);">
                        <i class="fas fa-chart-line" style="font-size: 2.5rem; opacity: 0.5;"></i>
                        <h3 style="margin: 15px 0 10px 0;">Ready to Reconcile</h3>
                        <p>Upload your files and click the button above to start</p>
                    </div>
                </div>
                
                <div id="summarySection"></div>
                <div id="unmatchedSection"></div>
                <div id="downloadSection"></div>
            </div>
        </div>
    </div>

    <script>
        let currentModule = '';
        let currentCurrency = '';
        let uploadedProcessors = [];

        // Navigation functions
        function showLandingPage() {
            document.getElementById('landingPage').classList.remove('hidden');
            document.getElementById('currencyPage').classList.add('hidden');
            document.getElementById('reconciliationPage').classList.add('hidden');
            updateOverallStats();
        }

        function showModule(module) {
            currentModule = module;
            const titles = {
                'collections': 'Collections Reconciliation',
                'payouts': 'Payouts Reconciliation', 
                'fund_transfers': 'Fund Transfers Reconciliation'
            };
            document.getElementById('moduleTitle').textContent = titles[module];
            document.getElementById('landingPage').classList.add('hidden');
            document.getElementById('currencyPage').classList.remove('hidden');
        }

        function showCurrencyPage() {
            document.getElementById('currencyPage').classList.remove('hidden');
            document.getElementById('reconciliationPage').classList.add('hidden');
            // Reset currency selection
            document.querySelectorAll('.currency-card').forEach(card => {
                card.classList.remove('selected');
            });
        }

        function selectCurrency(currency) {
            currentCurrency = currency;
            // Update UI
            document.querySelectorAll('.currency-card').forEach(card => {
                card.classList.remove('selected');
            });
            event.target.closest('.currency-card').classList.add('selected');
            
            // Show reconciliation page
            document.getElementById('currencyPage').classList.add('hidden');
            document.getElementById('reconciliationPage').classList.remove('hidden');
            
            const titles = {
                'collections': 'Collections',
                'payouts': 'Payouts',
                'fund_transfers': 'Fund Transfers'
            };
            document.getElementById('reconTitle').textContent = `${titles[currentModule]} Reconciliation - ${currency}`;
            document.getElementById('reconSubtitle').textContent = `${titles[currentModule]} • ${currency}`;
            
            // Reset uploaded processors for new session
            uploadedProcessors = [];
            updateProcessorList();
        }

        // Toggle custom field visibility
        function toggleInternalCustom() {
            const reportType = document.getElementById('internalReportType').value;
            const customFields = document.getElementById('internalCustomFields');
            customFields.style.display = reportType === 'custom' ? 'block' : 'none';
        }

        function toggleProcessorCustom() {
            const processorType = document.getElementById('processorType').value;
            const customFields = document.getElementById('processorCustomFields');
            customFields.style.display = processorType === 'custom' ? 'block' : 'none';
        }

        // File handling functions
        document.getElementById('internalFile').addEventListener('change', function(e) {
            document.getElementById('internalFileName').textContent = e.target.files[0] ? e.target.files[0].name : 'No file chosen';
        });

        document.getElementById('processorFile').addEventListener('change', function(e) {
            const files = e.target.files;
            document.getElementById('processorFileName').textContent = files.length === 0 ? 'No files chosen' : `${files.length} files selected`;
        });

        function updateProcessorList() {
            const processorList = document.getElementById('processorList');
            const processorItems = document.getElementById('processorItems');
            
            if (uploadedProcessors.length === 0) {
                processorList.style.display = 'none';
                return;
            }
            
            processorList.style.display = 'block';
            processorItems.innerHTML = uploadedProcessors.map(processor => `
                <div class="processor-item">
                    <div>
                        <div style="font-weight: 600; font-size: 0.9rem;">${processor.name}</div>
                        <div style="color: var(--gray); font-size: 0.8rem;">${processor.count} transactions</div>
                    </div>
                    <button onclick="removeProcessor('${processor.name}')" style="background: var(--danger); color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8rem;">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `).join('');
        }

        function removeProcessor(processorName) {
            uploadedProcessors = uploadedProcessors.filter(p => p.name !== processorName);
            updateProcessorList();
        }

        async function uploadFile(type) {
            const fileInput = document.getElementById(type + 'File');
            const messageDiv = document.getElementById(type + 'Message');
            
            if (type === 'processor') {
                const files = fileInput.files;
                if (files.length === 0) {
                    showMessage(messageDiv, 'Please select at least one file', 'error');
                    return;
                }

                const processorName = document.getElementById('processorName').value;
                if (!processorName) {
                    showMessage(messageDiv, 'Please enter processor name', 'error');
                    return;
                }

                try {
                    showMessage(messageDiv, 'Uploading...', 'warning');
                    
                    for (let file of files) {
                        const formData = new FormData();
                        formData.append('file', file);
                        formData.append('processor_name', processorName);
                        formData.append('module', currentModule);
                        formData.append('currency', currentCurrency);

                        const response = await fetch('/upload/processor', {
                            method: 'POST',
                            body: formData
                        });
                        const result = await response.json();
                        if (result.error) throw new Error(result.error);
                    }

                    uploadedProcessors.push({name: processorName, count: files.length});
                    showMessage(messageDiv, `${files.length} file(s) uploaded for ${processorName}`, 'success');
                    updateProcessorList();
                    
                    // Clear form
                    fileInput.value = '';
                    document.getElementById('processorFileName').textContent = 'No files chosen';
                    document.getElementById('processorName').value = '';
                    
                } catch (error) {
                    showMessage(messageDiv, `Upload failed: ${error}`, 'error');
                }
            } else {
                if (!fileInput.files[0]) {
                    showMessage(messageDiv, 'Please select a file', 'error');
                    return;
                }

                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('module', currentModule);
                formData.append('currency', currentCurrency);
                
                try {
                    showMessage(messageDiv, 'Uploading...', 'warning');
                    const response = await fetch('/upload/' + type, {
                        method: 'POST',
                        body: formData
                    });
                    const result = await response.json();
                    if (result.error) throw new Error(result.error);
                    showMessage(messageDiv, result.message, 'success');
                } catch (error) {
                    showMessage(messageDiv, `Upload failed: ${error}`, 'error');
                }
            }
        }

        async function runReconciliation() {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<div style="text-align: center; padding: 30px;"><i class="fas fa-cog fa-spin" style="font-size: 2rem; color: var(--primary);"></i><h3 style="margin: 15px 0;">Processing Reconciliation...</h3></div>';
            
            try {
                const response = await fetch('/reconcile', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        module: currentModule,
                        currency: currentCurrency
                    })
                });
                const data = await response.json();
                
                if (data.error) throw new Error(data.error);
                
                displayResults(data);
                updateOverallStats();
                
            } catch (error) {
                resultsDiv.innerHTML = `<div class="message error" style="text-align: center;">Error: ${error}</div>`;
            }
        }

        function displayResults(data) {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<h3 style="color: var(--success); text-align: center; margin-bottom: 20px;"><i class="fas fa-check-circle"></i> Reconciliation Complete</h3>';
            
            // Display summary with breakdowns
            const summary = data.summary;
            document.getElementById('summarySection').innerHTML = `
                <div class="stats-grid">
                    <div class="stat-card total">
                        <i class="fas fa-database stat-icon"></i>
                        <div class="stat-number">${summary.total_internal.toLocaleString()}</div>
                        <div class="stat-label">Total Internal</div>
                    </div>
                    <div class="stat-card total">
                        <i class="fas fa-database stat-icon"></i>
                        <div class="stat-number">${summary.total_processor.toLocaleString()}</div>
                        <div class="stat-label">Total Processor</div>
                    </div>
                    <div class="stat-card matched">
                        <i class="fas fa-check-circle stat-icon"></i>
                        <div class="stat-number">${summary.matched_count.toLocaleString()}</div>
                        <div class="stat-label">Matched</div>
                    </div>
                    <div class="stat-card unmatched">
                        <i class="fas fa-exclamation-triangle stat-icon"></i>
                        <div class="stat-number">${summary.unmatched_total.toLocaleString()}</div>
                        <div class="stat-label">Total Unmatched</div>
                    </div>
                </div>
            `;

            // Display unmatched breakdown by processor
            let unmatchedHTML = '<h3 style="margin: 20px 0 15px 0;"><i class="fas fa-exclamation-triangle" style="color: var(--warning);"></i> Unmatched Breakdown</h3>';
            
            if (data.unmatched_breakdown && data.unmatched_breakdown.processors) {
                unmatchedHTML += '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 12px 0;">';
                Object.entries(data.unmatched_breakdown.processors).forEach(([processor, stats]) => {
                    unmatchedHTML += `
                        <div style="background: white; padding: 12px; border-radius: 6px; box-shadow: var(--card-shadow); border-left: 4px solid var(--warning);">
                            <div style="font-weight: 600; color: var(--dark); font-size: 0.9rem;">${processor}</div>
                            <div style="color: var(--gray); font-size: 0.8rem;">Count: ${stats.count.toLocaleString()}</div>
                        </div>
                    `;
                });
                unmatchedHTML += '</div>';
            }

            unmatchedHTML += `<div style="background: white; padding: 12px; border-radius: 6px; box-shadow: var(--card-shadow); margin: 10px 0; border-left: 4px solid var(--danger);">
                <div style="font-weight: 600; color: var(--dark); font-size: 0.9rem;">Unmatched Internal</div>
                <div style="color: var(--gray); font-size: 0.8rem;">Count: ${summary.unmatched_internal_count.toLocaleString()}</div>
            </div>`;

            document.getElementById('unmatchedSection').innerHTML = unmatchedHTML;

            // Download section
            document.getElementById('downloadSection').innerHTML = `
                <div style="background: var(--primary); padding: 20px; border-radius: 6px; margin: 20px 0; text-align: center;">
                    <h3 style="color: white; margin-bottom: 15px; font-size: 1.1rem;"><i class="fas fa-download"></i> Download Reports</h3>
                    <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
                        <button onclick="downloadReport('matched')" class="btn" style="background: var(--success); padding: 8px 15px;">
                            <i class="fas fa-file-csv"></i> Matched Report
                        </button>
                        <button onclick="downloadReport('unmatched_internal')" class="btn" style="background: var(--warning); color: var(--dark); padding: 8px 15px;">
                            <i class="fas fa-file-excel"></i> Unmatched Internal
                        </button>
                        <button onclick="downloadReport('unmatched_processor')" class="btn" style="background: var(--danger); padding: 8px 15px;">
                            <i class="fas fa-file-export"></i> Unmatched Processor
                        </button>
                        <button onclick="downloadReport('full_reconciliation')" class="btn" style="background: white; color: var(--primary); padding: 8px 15px;">
                            <i class="fas fa-file-alt"></i> Full Report
                        </button>
                    </div>
                </div>
            `;
        }

        async function downloadReport(type) {
            try {
                const response = await fetch('/download/' + type, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        module: currentModule,
                        currency: currentCurrency
                    })
                });
                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${currentModule}_${currentCurrency}_${type}_${new Date().toISOString().split('T')[0]}.${type === 'full_reconciliation' ? 'xlsx' : 'csv'}`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                }
            } catch (error) {
                alert('Download error: ' + error);
            }
        }

        async function updateOverallStats() {
            try {
                const response = await fetch('/overall_stats');
                const data = await response.json();
                if (data.stats) {
                    const s = data.stats;
                    document.getElementById('totalReconciliations').textContent = s.total_reconciliations.toLocaleString();
                    document.getElementById('totalMatched').textContent = s.total_matched.toLocaleString();
                    document.getElementById('totalUnmatched').textContent = (s.total_unmatched_internal + s.total_unmatched_processor).toLocaleString();
                }
            } catch (error) {
                console.log('Could not update overall stats');
            }
        }

        function showMessage(container, message, type) {
            container.innerHTML = `<div class="message ${type}">${message}</div>`;
        }

        // Initialize
        updateOverallStats();
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return LANDING_HTML

@app.route('/overall_stats')
def overall_stats():
    """Get overall platform statistics"""
    stats = get_overall_statistics()
    return jsonify({'stats': stats})

@app.route('/upload/<file_type>', methods=['POST'])
def upload_file(file_type):
    """Handle file uploads for internal and processor reports"""
    try:
        module = request.form.get('module')
        currency = request.form.get('currency')
        
        if not module or not currency:
            return jsonify({'error': 'Module and currency are required'}), 400
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Read file
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file)
        else:
            return jsonify({'error': 'File must be CSV or Excel'}), 400
        
        if 'reference_number' not in df.columns or 'amount' not in df.columns:
            return jsonify({'error': 'File must have reference_number and amount columns'}), 400
        
        if 'description' not in df.columns:
            df['description'] = ''
        
        # Add currency to records
        records = df.to_dict('records')
        for record in records:
            record['currency'] = currency
        
        if file_type == 'internal':
            reconciliation_data[module][currency]['internal'] = records
            return jsonify({'message': f'Internal report loaded: {len(records):,} transactions'})
        
        elif file_type == 'processor':
            processor_name = request.form.get('processor_name', 'unknown')
            
            # Store in processor datasets
            if processor_name not in reconciliation_data[module][currency]['processors']:
                reconciliation_data[module][currency]['processors'][processor_name] = []
            reconciliation_data[module][currency]['processors'][processor_name].extend(records)
            
            # Also add to combined processor data
            for record in records:
                record['processor_name'] = processor_name
            reconciliation_data[module][currency]['processor_data'].extend(records)
            
            return jsonify({'message': f'{processor_name} data loaded: {len(records):,} transactions'})
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/reconcile', methods=['POST'])
def reconcile():
    """Run reconciliation for specific module and currency"""
    try:
        data = request.get_json()
        module = data.get('module')
        currency = data.get('currency')
        
        if not module or not currency:
            return jsonify({'error': 'Module and currency are required'}), 400
        
        internal_data = reconciliation_data[module][currency]['internal']
        processor_data = reconciliation_data[module][currency]['processor_data']
        processors = reconciliation_data[module][currency]['processors']
        
        # Use optimized matching
        matches, matched_references = find_matches_optimized(internal_data, processor_data)
        
        # Find unmatched transactions
        unmatched_internal = [
            {
                'reference': internal['reference_number'],
                'amount': float(internal['amount']),
                'description': internal.get('description', ''),
                'currency': internal.get('currency', '')
            }
            for internal in internal_data 
            if internal['reference_number'] not in matched_references
        ]
        
        unmatched_processor = [
            {
                'reference': processor['reference_number'],
                'amount': float(processor['amount']),
                'processor': processor['processor_name'],
                'description': processor.get('description', ''),
                'currency': processor.get('currency', '')
            }
            for processor in processor_data 
            if processor['reference_number'] not in matched_references
        ]
        
        # Calculate unmatched breakdown by processor
        unmatched_breakdown = {'processors': {}}
        for processor_name, processor_records in processors.items():
            unmatched_count = sum(1 for record in processor_records if record['reference_number'] not in matched_references)
            unmatched_value = sum(float(record['amount']) for record in processor_records if record['reference_number'] not in matched_references)
            if unmatched_count > 0:
                unmatched_breakdown['processors'][processor_name] = {
                    'count': unmatched_count,
                    'value': unmatched_value
                }
        
        # Calculate comprehensive summary
        total_internal = len(internal_data)
        total_processor = len(processor_data)
        total_internal_value = sum(float(internal['amount']) for internal in internal_data)
        total_processor_value = sum(float(processor['amount']) for processor in processor_data)
        matched_value = sum(match['internal_amount'] for match in matches)
        unmatched_internal_value = sum(txn['amount'] for txn in unmatched_internal)
        unmatched_processor_value = sum(txn['amount'] for txn in unmatched_processor)
        unmatched_total = len(unmatched_internal) + len(unmatched_processor)
        unmatched_total_value = unmatched_internal_value + unmatched_processor_value
        
        summary = {
            'total_internal': total_internal,
            'total_processor': total_processor,
            'total_internal_value': total_internal_value,
            'total_processor_value': total_processor_value,
            'matched_count': len(matches),
            'matched_value': matched_value,
            'unmatched_internal_count': len(unmatched_internal),
            'unmatched_internal_value': unmatched_internal_value,
            'unmatched_processor_count': len(unmatched_processor),
            'unmatched_processor_value': unmatched_processor_value,
            'unmatched_total': unmatched_total,
            'unmatched_total_value': unmatched_total_value
        }
        
        # Add to reconciliation history
        reconciliation_history.append({
            'module': module,
            'currency': currency,
            'timestamp': datetime.now().isoformat(),
            'matched_count': len(matches),
            'unmatched_internal_count': len(unmatched_internal),
            'unmatched_processor_count': len(unmatched_processor),
            'matched_value': matched_value,
            'unmatched_internal_value': unmatched_internal_value,
            'unmatched_processor_value': unmatched_processor_value
        })
        
        return jsonify({
            'matches': matches,
            'unmatched_internal': unmatched_internal,
            'unmatched_processor': unmatched_processor,
            'unmatched_breakdown': unmatched_breakdown,
            'summary': summary
        })
        
    except Exception as e:
        return jsonify({'error': f'Reconciliation failed: {str(e)}'}), 500

@app.route('/download/<report_type>', methods=['POST'])
def download_report(report_type):
    """Download reports for specific module and currency"""
    try:
        data = request.get_json()
        module = data.get('module')
        currency = data.get('currency')
        
        if not module or not currency:
            return jsonify({'error': 'Module and currency are required'}), 400
        
        # Re-run reconciliation to get current data
        recon_response = reconcile()
        reconciliation_result = recon_response.get_json()
        
        if 'error' in reconciliation_result:
            return jsonify({'error': reconciliation_result['error']}), 500
        
        internal_data = reconciliation_data[module][currency]['internal']
        processors = reconciliation_data[module][currency]['processors']
        
        if report_type == 'matched':
            df = pd.DataFrame(reconciliation_result['matches'])
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'{module}_{currency}_matched_{datetime.now().strftime("%Y%m%d")}.csv'
            )
            
        elif report_type == 'unmatched_internal':
            df = pd.DataFrame(reconciliation_result['unmatched_internal'])
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'{module}_{currency}_unmatched_internal_{datetime.now().strftime("%Y%m%d")}.csv'
            )
            
        elif report_type == 'unmatched_processor':
            df = pd.DataFrame(reconciliation_result['unmatched_processor'])
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'{module}_{currency}_unmatched_processor_{datetime.now().strftime("%Y%m%d")}.csv'
            )
            
        elif report_type == 'full_reconciliation':
            # Create comprehensive Excel report
            with pd.ExcelWriter('full_reconciliation.xlsx', engine='openpyxl') as writer:
                # Internal Report sheet
                if internal_data:
                    internal_df = pd.DataFrame(internal_data)
                    # Add match status
                    matched_refs = [match['reference'] for match in reconciliation_result['matches']]
                    internal_df['Match_Status'] = internal_df['reference_number'].isin(matched_refs).map({True: 'MATCHED', False: 'UNMATCHED'})
                    internal_df.to_excel(writer, sheet_name='Internal Report', index=False)
                
                # Processor Reports (separate sheets)
                for processor_name, records in processors.items():
                    processor_df = pd.DataFrame(records)
                    processor_df['Match_Status'] = processor_df['reference_number'].isin(matched_refs).map({True: 'MATCHED', False: 'UNMATCHED'})
                    sheet_name = processor_name[:31]  # Excel sheet name limit
                    processor_df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Matched Transactions sheet
                if reconciliation_result['matches']:
                    matched_df = pd.DataFrame(reconciliation_result['matches'])
                    matched_df.to_excel(writer, sheet_name='Matched Transactions', index=False)
                
                # Unmatched sheets
                if reconciliation_result['unmatched_internal']:
                    unmatched_int_df = pd.DataFrame(reconciliation_result['unmatched_internal'])
                    unmatched_int_df.to_excel(writer, sheet_name='Unmatched Internal', index=False)
                
                if reconciliation_result['unmatched_processor']:
                    unmatched_proc_df = pd.DataFrame(reconciliation_result['unmatched_processor'])
                    unmatched_proc_df.to_excel(writer, sheet_name='Unmatched Processor', index=False)
                
                # Summary sheet
                summary_data = {
                    'Metric': [
                        'Module', 'Currency', 'Total Internal Transactions', 'Total Processor Transactions',
                        'Matched Transactions', 'Unmatched Internal', 'Unmatched Processor',
                        'Total Internal Value', 'Total Processor Value', 'Matched Value',
                        'Unmatched Internal Value', 'Unmatched Processor Value', 'Reconciliation Date'
                    ],
                    'Value': [
                        module, currency,
                        f"{reconciliation_result['summary']['total_internal']:,}",
                        f"{reconciliation_result['summary']['total_processor']:,}",
                        f"{reconciliation_result['summary']['matched_count']:,}",
                        f"{reconciliation_result['summary']['unmatched_internal_count']:,}",
                        f"{reconciliation_result['summary']['unmatched_processor_count']:,}",
                        f"${reconciliation_result['summary']['total_internal_value']:,.2f}",
                        f"${reconciliation_result['summary']['total_processor_value']:,.2f}",
                        f"${reconciliation_result['summary']['matched_value']:,.2f}",
                        f"${reconciliation_result['summary']['unmatched_internal_value']:,.2f}",
                        f"${reconciliation_result['summary']['unmatched_processor_value']:,.2f}",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Send the Excel file
            with open('full_reconciliation.xlsx', 'rb') as f:
                excel_data = f.read()
            os.remove('full_reconciliation.xlsx')
            
            return send_file(
                io.BytesIO(excel_data),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'{module}_{currency}_full_reconciliation_{datetime.now().strftime("%Y%m%d")}.xlsx'
            )
            
        else:
            return jsonify({'error': 'Invalid report type'}), 400
        
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

if __name__ == '__main__':
    print("\n🏦 Starting Multi-Currency Reconciliation Platform...")
    print("📊 Modules: Collections, Payouts, Fund Transfers")
    print("💰 Currencies: UGX, NGN, TZS, KES, GHS, ZMW, ZAR")
    print("🌐 Open: http://localhost:5000")
    print("⏳ Starting server...\n")
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)