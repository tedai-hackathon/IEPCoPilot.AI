function enableReq() {
	const recSection = document.getElementById("consent");
	if(recSection.checked == true){
		document.getElementById("recordButton").style.display="block";
	}
	else
	{
		document.getElementById("recordButton").style.display="none";
	}
}