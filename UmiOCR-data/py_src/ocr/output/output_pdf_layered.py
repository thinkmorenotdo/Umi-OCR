# 双层可搜索 searchable pdf
# https://github.com/pymupdf/PyMuPDF/discussions/2299

from .output import Output

import os
import fitz  # PyMuPDF


class OutputPdfLayered(Output):
    def __init__(self, argd):
        self.dir = argd["outputDir"]  # 输出路径（文件夹）
        self.originPath = argd["originPath"]  # 原始文件路径
        self.fileName = argd["outputFileName"]  # 文件名
        self.outputPath = f"{self.dir}/{self.fileName}.layered.pdf"  # 输出路径
        self.pdf = None
        try:
            self.font = fitz.Font("cjk")  # 字体
        except Exception as e:
            raise Exception(f"Failed to load cjk font. {e}\n无法加载cjk字体。")
        try:
            self.pdf = self._getPDF(self.originPath)  # 加载pymupdf对象
        except Exception as e:
            raise Exception(
                f"Failed to load doc file. {e}\n无法加载文档。\n{self.originPath}"
            )

    # 获取pdf文档对象，或将其它类型的文档转为PDF对象
    def _getPDF(self, path):
        # https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/convert-document/convert.py
        doc = fitz.open(path)
        if doc.is_pdf:
            return doc
        b = doc.convert_to_pdf()  # 转换为PDF格式的二进制数据
        pdf = fitz.open("pdf", b)  # 创建PDF文档对象
        pdf.set_toc(doc.get_toc())  # 复制原始文档的目录
        # 复制原始文档的元数据（如作者、标题等）
        meta = doc.metadata
        if not meta["producer"]:
            meta["producer"] = "Umi-OCR & PyMuPDF v" + fitz.VersionBind
        if not meta["creator"]:
            meta["creator"] = "Umi-OCR & PyMuPDF PDF converter"
        pdf.set_metadata(meta)
        # 复制原始文档的链接
        for pinput in doc:
            links = pinput.get_links()
            pout = pdf[pinput.number]
            for l in links:
                if l["kind"] == fitz.LINK_NAMED:  # 不处理 named links
                    continue
                pout.insert_link(l)  # 写入新文档
        doc.close()  # 释放原文档
        return pdf

    # 计算填满宽和高的一行字体大小
    def _calculateFontSize(self, text, w, h):
        if h > w:  # 竖排转为横排计算
            w, h = h, w
        fontsize = round(h)  # 字体大小初值，假设为行高
        minSize = 5  # 大小下限
        getLen = lambda text, s: self.font.text_length(text, fontsize=s)
        while getLen(text, fontsize) > w and fontsize >= minSize:
            fontsize -= 1  # 尝试减小字体，直到行宽刚好小于界限
        while getLen(text, fontsize) < w:
            fontsize += 1  # 尝试增大字体，直到行宽刚好超过界限
        while getLen(text, fontsize) > w and fontsize >= minSize:
            fontsize -= 0.1  # 再次减小字体，将精度提升到 0.1
        return fontsize

    def print(self, res):  # 输出图片结果
        if not self.pdf:
            print("[Error] PDF对象未初始化！")
            return
        if not res["code"] == 100:
            return  # 忽略空白

        pno = res["page"] - 1  # 当前页数
        page = self.pdf[pno]  # 当前页对象
        page.insert_font(fontname="cjk", fontbuffer=self.font.buffer)  # 页面插入字体
        # shape = page.new_shape()  # 页面创建新形状
        # 插入文本，用shape.insert_text（可编辑）或page.insert_text（不可编辑）
        for tb in res["data"]:
            if "from" in tb and tb["from"] == "text":
                continue  # 跳过直接提取的文本，只写入OCR文本
            text = tb["text"]
            box = tb["box"]
            x0, y0 = box[0]
            x2, y2 = box[2]
            w = x2 - x0
            h = y2 - y0
            fontsize = self._calculateFontSize(text, w, h)
            # shape.insert_text(
            page.insert_text(
                (x0, y2),
                text,
                fontsize,
                fontname="cjk",
                rotate=0,  # 旋转
                stroke_opacity=0,  # 描边透明度
                fill_opacity=0,  # 填充（字体）透明度
            )
        # shape.commit()

    def onEnd(self):  # 结束时保存。
        print("保存PDF：", self.outputPath)
        if self.pdf:
            try:  # 对于部分PDF，如用txt直接打印的，构建字体子集会失败。
                self.pdf.subset_fonts()  # 构建字体子集，减小文件大小。需要 fontTools 库
            except Exception as e:  # TODO: 失败原因？可能文件中实际并没有字体？
                print("[Warning] 构建字体子集失败：", e)
            # ez_save默认启用压缩和垃圾回收 deflate=True, garbage=3
            self.pdf.ez_save(self.outputPath)
        self.pdf.close()
