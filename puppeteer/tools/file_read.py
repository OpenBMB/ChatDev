from tools.base.register import global_tool_registry
from tools.base.base_tool import Tool
from tenacity import retry, stop_after_attempt, wait_fixed
import os
from tools.utils.converter import MarkdownConverter
from model import global_openai_client as client

@global_tool_registry("read_file")
class FileRead(Tool):
    """
    support file type:
    .csv .xlsx
    .docx
    .txt
    .pdf
    (LLM generate description).png .jpg .jpeg
    (LLM generate transcript).mp3
    .json .jsonld
    .pptx
    .wav
    .html .htm
    """
    
    def __init__(self, name):
        super().__init__(name=name, 
                         description="read file from local path", 
                         execute_function=self.execute)
        self.converter = MarkdownConverter(mlm_client=client)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def execute(self, *args,**kwargs):
        try:
            file_path = kwargs.get("file_path","")
            file_extension = kwargs.get("file_extension", "")
            if not os.path.exists(file_path):
                return False, "File Not Exists"
            try:
                ans = self.converter.convert_local(path=file_path, 
                                                   file_extension=file_extension)
                return True, ans.text_content
            except Exception as e:
                return False, f"Error processing file: {str(e)}"
        except Exception as e:
            return False, f"Error processing file: {str(e)}"