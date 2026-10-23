param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$wordNs = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

function Read-ZipXml {
    param([object]$Archive, [string]$EntryName)
    $entry = $Archive.GetEntry($EntryName)
    if ($null -eq $entry) {
        throw "Missing DOCX part: $EntryName"
    }
    $reader = [System.IO.StreamReader]::new($entry.Open())
    try {
        [xml]$reader.ReadToEnd()
    }
    finally {
        $reader.Dispose()
    }
}

function Write-ZipXml {
    param([object]$Archive, [string]$EntryName, [xml]$Xml)
    $oldEntry = $Archive.GetEntry($EntryName)
    if ($null -ne $oldEntry) {
        $oldEntry.Delete()
    }
    $entry = $Archive.CreateEntry($EntryName, [System.IO.Compression.CompressionLevel]::Optimal)
    $writer = [System.IO.StreamWriter]::new($entry.Open(), [System.Text.UTF8Encoding]::new($false))
    try {
        $Xml.Save($writer)
    }
    finally {
        $writer.Dispose()
    }
}

function Get-NodeText {
    param([System.Xml.XmlNode]$Node, [System.Xml.XmlNamespaceManager]$Ns)
    return (($Node.SelectNodes('.//w:t', $Ns) | ForEach-Object { $_.InnerText }) -join '')
}

function Set-NodeText {
    param(
        [System.Xml.XmlNode]$Node,
        [string]$Text,
        [System.Xml.XmlNamespaceManager]$Ns
    )
    $textNodes = @($Node.SelectNodes('.//w:t', $Ns))
    if ($textNodes.Count -eq 0) {
        throw 'The target node has no text run.'
    }
    $textNodes[0].InnerText = $Text
    for ($i = 1; $i -lt $textNodes.Count; $i++) {
        $textNodes[$i].InnerText = ''
    }
}

function Set-ParagraphText {
    param(
        [System.Xml.XmlElement]$Paragraph,
        [string]$Text,
        [xml]$DocumentXml,
        [System.Xml.XmlNamespaceManager]$Ns
    )

    $pPr = $Paragraph.SelectSingleNode('./w:pPr', $Ns)
    $firstRun = $Paragraph.SelectSingleNode('./w:r', $Ns)
    $runProperties = $null
    if ($null -ne $firstRun) {
        $sourceRPr = $firstRun.SelectSingleNode('./w:rPr', $Ns)
        if ($null -ne $sourceRPr) {
            $runProperties = $sourceRPr.CloneNode($true)
        }
    }

    foreach ($child in @($Paragraph.ChildNodes)) {
        if ($child -ne $pPr) {
            [void]$Paragraph.RemoveChild($child)
        }
    }

    $run = $DocumentXml.CreateElement('w', 'r', $wordNs)
    if ($null -ne $runProperties) {
        [void]$run.AppendChild($runProperties)
    }
    $textNode = $DocumentXml.CreateElement('w', 't', $wordNs)
    $textNode.InnerText = $Text
    [void]$run.AppendChild($textNode)
    [void]$Paragraph.AppendChild($run)
}

$resolvedInput = (Resolve-Path -LiteralPath $InputPath).Path
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
Copy-Item -LiteralPath $resolvedInput -Destination $resolvedOutput -Force

$archive = [System.IO.Compression.ZipFile]::Open($resolvedOutput, [System.IO.Compression.ZipArchiveMode]::Update)
try {
    $documentXml = Read-ZipXml $archive 'word/document.xml'
    $settingsXml = Read-ZipXml $archive 'word/settings.xml'
    $stylesXml = Read-ZipXml $archive 'word/styles.xml'
    $appXml = Read-ZipXml $archive 'docProps/app.xml'
    $footerXml = Read-ZipXml $archive 'word/footer1.xml'

    $ns = [System.Xml.XmlNamespaceManager]::new($documentXml.NameTable)
    $ns.AddNamespace('w', $wordNs)

    # 1) Make the manually authored contents occupy two pages, matching the PDF.
    $tables = @($documentXml.SelectNodes('//w:tbl', $ns))
    if ($tables.Count -lt 5) {
        throw "Unexpected table count: $($tables.Count)"
    }
    $toc = $tables[2]
    $tocRows = @($toc.SelectNodes('./w:tr', $ns))
    if ($tocRows.Count -ne 28) {
        throw "Unexpected TOC row count: $($tocRows.Count)"
    }

    $secondToc = $toc.CloneNode($true)
    $secondRows = @($secondToc.SelectNodes('./w:tr', $ns))
    for ($i = 21; $i -ge 0; $i--) {
        [void]$secondToc.RemoveChild($secondRows[$i])
    }
    for ($i = $tocRows.Count - 1; $i -ge 22; $i--) {
        [void]$toc.RemoveChild($tocRows[$i])
    }

    $pageBreakParagraph = $documentXml.CreateElement('w', 'p', $wordNs)
    $run = $documentXml.CreateElement('w', 'r', $wordNs)
    $break = $documentXml.CreateElement('w', 'br', $wordNs)
    $break.SetAttribute('type', $wordNs, 'page')
    [void]$run.AppendChild($break)
    [void]$pageBreakParagraph.AppendChild($run)
    [void]$toc.ParentNode.InsertAfter($pageBreakParagraph, $toc)
    [void]$toc.ParentNode.InsertAfter($secondToc, $pageBreakParagraph)

    # 2) Correct manual TOC labels and Roman page numbers to match the PDF.
    $tocTables = @($toc, $secondToc)
    foreach ($tocTable in $tocTables) {
        foreach ($row in @($tocTable.SelectNodes('./w:tr', $ns))) {
            $cells = @($row.SelectNodes('./w:tc', $ns))
            if ($cells.Count -lt 2) { continue }
            $label = Get-NodeText $cells[0] $ns
            switch ($label) {
                'DANH MỤC HÌNH VẼ' { Set-NodeText $cells[1] 'iv' $ns }
                'DANH MỤC BẢNG' { Set-NodeText $cells[1] 'v' $ns }
                'CHƯƠNG 1. GIỚI THIỆU ĐƠN VỊ THỰC TẬP' { Set-NodeText $cells[0] '1   GIỚI THIỆU ĐƠN VỊ THỰC TẬP' $ns }
                'CHƯƠNG 2. NỘI DUNG THỰC TẬP' { Set-NodeText $cells[0] '2   NỘI DUNG THỰC TẬP' $ns }
                'CHƯƠNG 3. NHẬN XÉT VÀ ĐỀ XUẤT' { Set-NodeText $cells[0] '3   NHẬN XÉT VÀ ĐỀ XUẤT' $ns }
                'PHỤ LỤC A. THÔNG TIN PHỤC VỤ PHIẾU ĐÁNH GIÁ' { Set-NodeText $cells[0] 'A   THÔNG TIN PHỤC VỤ PHIẾU ĐÁNH GIÁ' $ns }
                'PHỤ LỤC B. MINH CHỨNG THỰC TẬP' { Set-NodeText $cells[0] 'B   MINH CHỨNG THỰC TẬP' $ns }
            }
        }
    }

    # 3) Match List of Figures/Tables numbering style (without repeated prefixes).
    foreach ($row in @($tables[3].SelectNodes('./w:tr', $ns))) {
        $cell = $row.SelectSingleNode('./w:tc[1]', $ns)
        $label = Get-NodeText $cell $ns
        Set-NodeText $cell ($label -replace '^Hình\s+', '') $ns
    }
    foreach ($row in @($tables[4].SelectNodes('./w:tr', $ns))) {
        $cell = $row.SelectSingleNode('./w:tc[1]', $ns)
        $label = Get-NodeText $cell $ns
        Set-NodeText $cell ($label -replace '^Bảng\s+', '') $ns
    }

    # 4) Replace the conclusion with the final four-paragraph version.
    $body = $documentXml.SelectSingleNode('//w:body', $ns)
    $bodyParagraphs = @($body.SelectNodes('./w:p', $ns))
    $conclusionHeading = $bodyParagraphs | Where-Object { (Get-NodeText $_ $ns) -eq 'KẾT LUẬN' } | Select-Object -Last 1
    if ($null -eq $conclusionHeading) {
        throw 'Conclusion heading not found.'
    }
    $firstConclusion = $conclusionHeading.NextSibling
    while ($null -ne $firstConclusion -and $firstConclusion.LocalName -ne 'p') {
        $firstConclusion = $firstConclusion.NextSibling
    }
    $secondConclusion = $firstConclusion.NextSibling
    while ($null -ne $secondConclusion -and $secondConclusion.LocalName -ne 'p') {
        $secondConclusion = $secondConclusion.NextSibling
    }

    $conclusionTexts = @(
        'Qua đợt thực tập, em đã tìm hiểu được tổng quan về Công ty Cổ phần TECHPAL – từ quá trình hình thành, các lĩnh vực hoạt động cho đến cơ cấu tổ chức. Phần em tập trung nhiều nhất là hoạt động cung ứng linh kiện điện tử và thiết bị tự động hóa. Qua đó, em hiểu rõ hơn vai trò của việc đọc đúng mã hàng, đối chiếu datasheet và giữ thông tin kỹ thuật nhất quán giữa các bộ phận liên quan.',
        'Kết quả cụ thể của quá trình tìm hiểu là em đã phân loại bốn nhóm sản phẩm trong danh mục TECHPAL, lập bảng kiểm trước khi lựa chọn mã hàng và tra cứu bốn mã đại diện gồm MAX487CSA+T, BMXAMI0410, 6ES7153-1AA03-0XB0 và CR1000X. Bài toán giám sát nhiệt độ tủ kỹ thuật giúp em thử đi từ yêu cầu ban đầu đến sơ đồ khối, sau đó xem từng loại thiết bị có thể đảm nhận vai trò nào. Phương án này mới dừng ở mức khảo sát trên giấy, chưa có nguyên mẫu và số liệu đo thực tế, nhưng giúp em nhìn rõ hơn sự khác nhau giữa một IC giao tiếp, mô-đun PLC và bộ ghi dữ liệu chuyên dụng.',
        'Bài học lớn nhất em rút ra là không thể chọn linh kiện chỉ dựa vào tên gọi hoặc mô tả ngắn trên trang bán hàng. Ngoài thông số điện, còn phải kiểm tra kiểu vỏ, đầu nối, khả năng tương thích, điều kiện môi trường và trạng thái vòng đời của sản phẩm. Chỉ một hậu tố bị bỏ sót cũng có thể dẫn đến sai quy cách đóng gói hoặc sai biến thể cần đặt mua.',
        'Do thời gian và điều kiện tiếp cận còn hạn chế, báo cáo chưa đi sâu vào quy trình nội bộ, kiểm tra hàng hóa hoặc thử nghiệm một hệ thống hoàn chỉnh. Nếu có điều kiện tiếp tục, em muốn hoàn thiện bảng so sánh cho các mã đã chọn và làm một mô hình đo nhiệt độ nhỏ để kiểm tra lại phương án trên thực tế. Những kinh nghiệm từ đợt thực tập sẽ là cơ sở để em học tốt hơn các nội dung về thiết kế mạch, hệ thống nhúng và tự động hóa trong thời gian tới.'
    )

    Set-ParagraphText $firstConclusion $conclusionTexts[0] $documentXml $ns
    Set-ParagraphText $secondConclusion $conclusionTexts[1] $documentXml $ns
    $thirdConclusion = $secondConclusion.CloneNode($true)
    Set-ParagraphText $thirdConclusion $conclusionTexts[2] $documentXml $ns
    [void]$body.InsertAfter($thirdConclusion, $secondConclusion)
    $fourthConclusion = $secondConclusion.CloneNode($true)
    Set-ParagraphText $fourthConclusion $conclusionTexts[3] $documentXml $ns
    [void]$body.InsertAfter($fourthConclusion, $thirdConclusion)

    # 5) Replace A.2 with the final, evidence-safe wording.
    $oldA2Start = 'Tìm hiểu cơ cấu tổ chức và các lĩnh vực hoạt động của Công ty Cổ phần TECHPAL.'
    $a2Paragraph = @($body.SelectNodes('./w:p', $ns)) | Where-Object { (Get-NodeText $_ $ns).StartsWith($oldA2Start) } | Select-Object -Last 1
    if ($null -eq $a2Paragraph) {
        throw 'Appendix A.2 paragraph not found.'
    }
    $a2Text = 'Tìm hiểu cơ cấu tổ chức và các lĩnh vực hoạt động của Công ty Cổ phần TECHPAL. Khảo sát danh mục linh kiện điện tử và thiết bị tự động hóa công nghiệp. Tìm hiểu phương pháp đọc mã linh kiện, datasheet và các tiêu chí kỹ thuật khi lựa chọn thiết bị. Đối chiếu một số mã sản phẩm đại diện với tài liệu của nhà sản xuất và xây dựng bảng kiểm kỹ thuật trước khi lựa chọn thiết bị. Xây dựng yêu cầu và sơ đồ khối minh họa cho hệ thống giám sát nhiệt độ tủ kỹ thuật. Tổng hợp kết quả, nhận xét nhược điểm và đề xuất hướng hoàn thiện.'
    Set-ParagraphText $a2Paragraph $a2Text $documentXml $ns

    # 6) Upgrade compatibility and make Times New Roman explicit for every script.
    $settingsNs = [System.Xml.XmlNamespaceManager]::new($settingsXml.NameTable)
    $settingsNs.AddNamespace('w', $wordNs)
    $compat = $settingsXml.SelectSingleNode('//w:compatSetting[@w:name="compatibilityMode"]', $settingsNs)
    if ($null -ne $compat) {
        [void]$compat.SetAttribute('val', $wordNs, '15')
    }

    $stylesNs = [System.Xml.XmlNamespaceManager]::new($stylesXml.NameTable)
    $stylesNs.AddNamespace('w', $wordNs)
    foreach ($fonts in @($stylesXml.SelectNodes('//w:rFonts', $stylesNs))) {
        [void]$fonts.SetAttribute('ascii', $wordNs, 'Times New Roman')
        [void]$fonts.SetAttribute('hAnsi', $wordNs, 'Times New Roman')
        [void]$fonts.SetAttribute('eastAsia', $wordNs, 'Times New Roman')
        [void]$fonts.SetAttribute('cs', $wordNs, 'Times New Roman')
    }

    # The converter duplicated the PAGE field in the shared footer, which makes
    # Word display page 14 as "1414". Keep exactly one PAGE field per paragraph.
    $footerNs = [System.Xml.XmlNamespaceManager]::new($footerXml.NameTable)
    $footerNs.AddNamespace('w', $wordNs)
    foreach ($paragraph in @($footerXml.SelectNodes('//w:p', $footerNs))) {
        $pageFields = @($paragraph.SelectNodes('.//w:fldSimple[contains(@w:instr, "PAGE")]', $footerNs))
        for ($i = $pageFields.Count - 1; $i -ge 1; $i--) {
            $fieldRun = $pageFields[$i].ParentNode
            [void]$fieldRun.ParentNode.RemoveChild($fieldRun)
        }
    }

    # The source contains duplicate roman + decimal numbering in its final section.
    # Keep only decimal numbering for the main-matter/final section.
    $sectionProperties = @($documentXml.SelectNodes('//w:sectPr', $ns))
    foreach ($pageNumbering in @($documentXml.SelectNodes('//w:pgNumType', $ns))) {
        if ($pageNumbering.GetAttribute('fmt', $wordNs) -eq 'roman') {
            [void]$pageNumbering.SetAttribute('fmt', $wordNs, 'lowerRoman')
        }
    }
    $finalSection = $sectionProperties[-1]
    foreach ($pageNumbering in @($finalSection.SelectNodes('./w:pgNumType', $ns))) {
        if ($pageNumbering.GetAttribute('fmt', $wordNs) -ne 'decimal') {
            [void]$finalSection.RemoveChild($pageNumbering)
        }
    }

    if ($null -ne $appXml.Properties.Pages) {
        $appXml.Properties.Pages = '24'
    }
    if ($null -ne $appXml.Properties.Application) {
        $appXml.Properties.Application = 'Microsoft Office Word'
    }
    if ($null -ne $appXml.Properties.AppVersion) {
        $appXml.Properties.AppVersion = '16.0000'
    }

    Write-ZipXml $archive 'word/document.xml' $documentXml
    Write-ZipXml $archive 'word/settings.xml' $settingsXml
    Write-ZipXml $archive 'word/styles.xml' $stylesXml
    Write-ZipXml $archive 'word/footer1.xml' $footerXml
    Write-ZipXml $archive 'docProps/app.xml' $appXml
}
finally {
    $archive.Dispose()
}

Write-Output ('Created: ' + $resolvedOutput)

